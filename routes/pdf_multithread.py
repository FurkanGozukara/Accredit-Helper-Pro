"""
Simplified Multi-threaded PDF generation module for Accredit Helper Pro
This version fixes the timeout issues and Flask context problems
"""

import asyncio
import concurrent.futures
import json
import logging
import math
import os
import tempfile
import threading
import zipfile
from datetime import datetime
from io import BytesIO

from flask import request
from playwright.async_api import async_playwright


def split_students_into_chunks(student_ids, thread_count):
    """Pre-calculate student distribution across threads"""
    student_list = sorted(list(student_ids))
    chunk_size = math.ceil(len(student_list) / thread_count)
    chunks = [student_list[i:i + chunk_size] for i in range(0, len(student_list), chunk_size)]
    
    print(f"DEBUG: Student distribution across {thread_count} threads:")
    for i, chunk in enumerate(chunks):
        print(f"  Thread {i}: {len(chunk)} students ({chunk[0] if chunk else 'empty'} - {chunk[-1] if chunk else 'empty'})")
    
    return chunks


def generate_student_pdfs_multithreaded(student_ids, filter_year, search_query, filter_student_id, 
                                      include_graduating_only, display_method, orientation='landscape', 
                                      page_size='A4', thread_count=4):
    """Generate PDF reports using multi-threading"""
    try:
        logging.info(f"Starting multi-threaded PDF generation for {len(student_ids)} students using {thread_count} threads")
        print(f"DEBUG: Starting multi-threaded PDF generation for {len(student_ids)} students using {thread_count} threads")
        
        # Get Flask context information that threads will need
        base_url = request.url_root.rstrip('/')
        
        # Pre-fetch all student names while we have Flask context
        from routes.calculation_routes import get_student_name
        student_names = {}
        for student_id in student_ids:
            try:
                student_names[student_id] = get_student_name(student_id)
            except Exception as e:
                print(f"DEBUG: Error getting name for student {student_id}: {e}")
                student_names[student_id] = f"Student_{student_id}"
        
        print(f"DEBUG: Pre-fetched {len(student_names)} student names")
        
        # Get existing progress file from session
        from flask import session
        progress_file = session.get('pdf_progress_file')
        if not progress_file:
            progress_id = f"pdf_generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            progress_file = os.path.join(tempfile.gettempdir(), f"pdf_progress_{progress_id}.txt")
            session['pdf_progress_file'] = progress_file
        
        # Create timestamped directory for this run
        timestamp = datetime.now().strftime('%d_%B_%Y_%H_%M_%p')
        student_pdfs_dir = os.path.join(os.getcwd(), 'student_pdfs', timestamp)
        os.makedirs(student_pdfs_dir, exist_ok=True)
        
        # Initialize progress tracking
        progress_data = {
            'current': 0,
            'total': len(student_ids),
            'status': 'processing',
            'message': f'Starting multi-threaded PDF generation with {thread_count} threads...',
            'completed': False,
            'error': None,
            'timestamp': datetime.now().isoformat(),
            'threads': {}
        }
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(progress_data))
        
        # Split students into chunks
        student_chunks = split_students_into_chunks(student_ids, thread_count)
        
        # Progress lock for thread-safe updates
        progress_lock = threading.Lock()
        
        # Track results
        all_pdf_files = []
        total_successful = 0
        total_retry_rounds = 0
        
        # Use ThreadPoolExecutor for multi-threading
        with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
            # Submit all chunks to threads
            futures = []
            for i, student_chunk in enumerate(student_chunks):
                if student_chunk:  # Only submit non-empty chunks
                    future = executor.submit(
                        generate_student_pdfs_chunk_simple,
                        student_chunk,
                        filter_year,
                        search_query,
                        filter_student_id,
                        include_graduating_only,
                        display_method,
                        orientation,
                        page_size,
                        student_pdfs_dir,
                        progress_file,
                        i,
                        len(student_ids),
                        progress_lock,
                        base_url,
                        student_names
                    )
                    futures.append(future)
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    chunk_result = future.result()
                    all_pdf_files.extend(chunk_result['pdf_files'])
                    total_successful += chunk_result['successful_count']
                    total_retry_rounds += chunk_result['retry_rounds']
                    print(f"DEBUG: Chunk {chunk_result['chunk_index']} completed: {chunk_result['successful_count']} successful after {chunk_result['retry_rounds']} retry rounds")
                except Exception as e:
                    logging.error(f"Error in PDF generation chunk: {e}")
                    print(f"DEBUG: Error in PDF generation chunk: {e}")
        
        if total_successful != len(student_ids):
            return {
                'success': False,
                'error': f'Not all PDFs were generated successfully. Expected {len(student_ids)}, got {total_successful}'
            }
        
        # Combine all PDFs into a single PDF
        combined_pdf = None
        try:
            combined_pdf = combine_pdfs(all_pdf_files)
            if combined_pdf:
                combined_path = os.path.join(student_pdfs_dir, 'combined_all_students.pdf')
                with open(combined_path, 'wb') as f:
                    f.write(combined_pdf)
                logging.info(f"Combined PDF saved: {combined_path}")
        except Exception as e:
            logging.error(f"Error combining PDFs: {e}")
        
        # Create ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all individual PDFs
            for pdf_path in all_pdf_files:
                zip_file.write(pdf_path, os.path.basename(pdf_path))
            
            # Add combined PDF
            if combined_pdf:
                combined_path = os.path.join(student_pdfs_dir, 'combined_all_students.pdf')
                if os.path.exists(combined_path):
                    zip_file.write(combined_path, 'combined_all_students.pdf')
        
        zip_buffer.seek(0)
        
        # Mark progress as completed
        final_progress = {
            'current': len(student_ids),
            'total': len(student_ids),
            'status': 'completed',
            'message': f'Multi-threaded PDF generation completed! ALL {total_successful}/{len(student_ids)} students successful using {thread_count} threads (total retry rounds: {total_retry_rounds})',
            'completed': True,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(final_progress))
        
        logging.info(f"Multi-threaded PDF generation completed: ALL {total_successful}/{len(student_ids)} successful using {thread_count} threads after {total_retry_rounds} total retry rounds")
        
        return {
            'success': True,
            'zip_content': zip_buffer.getvalue(),
            'combined_pdf': combined_pdf,
            'output_directory': student_pdfs_dir,
            'successful_count': total_successful,
            'total_count': len(student_ids),
            'thread_count': thread_count
        }
        
    except Exception as e:
        logging.error(f"Error in multi-threaded PDF generation: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def generate_student_pdfs_chunk_simple(student_chunk, filter_year, search_query, filter_student_id, 
                                     include_graduating_only, display_method, orientation, page_size, 
                                     student_pdfs_dir, progress_file, chunk_index, total_students, 
                                     progress_lock, base_url, student_names):
    """Generate PDFs for a chunk of students with retry logic until all succeed"""
    pdf_files = []
    successful_count = 0
    
    print(f"DEBUG: Thread {chunk_index} starting with {len(student_chunk)} students")
    
    # Keep retrying failed students until all succeed
    remaining_students = list(enumerate(student_chunk))
    retry_count = 0
    
    while remaining_students:
        failed_students = []
        retry_count += 1
        
        if retry_count > 1:
            print(f"DEBUG: Thread {chunk_index} - Retry round {retry_count} for {len(remaining_students)} students")
            
        for original_index, student_id in remaining_students:
            try:
                print(f"DEBUG: Thread {chunk_index} - Processing student {student_id} (attempt {retry_count})")
                
                # Generate PDF for this student
                pdf_content = generate_student_pdf_with_playwright_simple(
                    student_id, filter_year, search_query, filter_student_id, 
                    include_graduating_only, display_method, orientation, page_size, base_url
                )
                
                if pdf_content:
                    # Get student name from pre-fetched names
                    student_name = student_names.get(student_id, f"Student_{student_id}")
                    safe_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    filename = f"{student_id}_{safe_name}.pdf".replace(' ', '_')
                    
                    # Save PDF to individual file
                    pdf_path = os.path.join(student_pdfs_dir, filename)
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_content)
                    
                    pdf_files.append(pdf_path)
                    successful_count += 1
                    print(f"DEBUG: Thread {chunk_index} - Successfully generated PDF for student {student_id}: {filename}")
                    
                    # Update progress immediately on success
                    with progress_lock:
                        try:
                            # Read current progress
                            if os.path.exists(progress_file):
                                with open(progress_file, 'r', encoding='utf-8') as f:
                                    progress_data = json.loads(f.read())
                            else:
                                progress_data = {'current': 0, 'total': total_students, 'threads': {}}
                            
                            # Update progress
                            progress_data['current'] = progress_data.get('current', 0) + 1
                            progress_data['message'] = f'Thread {chunk_index} succeeded for student {student_id} ({progress_data["current"]}/{total_students}) - Retry round {retry_count}'
                            progress_data['timestamp'] = datetime.now().isoformat()
                            
                            # Update thread-specific progress
                            if 'threads' not in progress_data:
                                progress_data['threads'] = {}
                            
                            progress_data['threads'][str(chunk_index)] = {
                                'processed': successful_count,
                                'total': len(student_chunk),
                                'successful': successful_count,
                                'current_student': student_id,
                                'retry_round': retry_count,
                                'remaining': len(remaining_students) - 1
                            }
                            
                            # Write updated progress
                            with open(progress_file, 'w', encoding='utf-8') as f:
                                f.write(json.dumps(progress_data))
                                
                            print(f"DEBUG: Thread {chunk_index} - Updated progress to {progress_data['current']}/{total_students}")
                        except Exception as progress_error:
                            print(f"DEBUG: Thread {chunk_index} - Progress update error: {progress_error}")
                            
                else:
                    print(f"DEBUG: Thread {chunk_index} - Failed to generate PDF for student {student_id} (attempt {retry_count})")
                    failed_students.append((original_index, student_id))
                    
            except Exception as e:
                print(f"DEBUG: Thread {chunk_index} - Error generating PDF for student {student_id} (attempt {retry_count}): {e}")
                failed_students.append((original_index, student_id))
                
        # Update remaining students list with failed ones
        remaining_students = failed_students
        
        if remaining_students:
            print(f"DEBUG: Thread {chunk_index} - {len(remaining_students)} students failed in round {retry_count}, retrying...")
            # Brief delay before retry
            import time
            time.sleep(5)  # 5 second delay between retry rounds
    
    print(f"DEBUG: Thread {chunk_index} completed - ALL {successful_count}/{len(student_chunk)} students successful after {retry_count} retry rounds")
    
    return {
        'pdf_files': pdf_files,
        'successful_count': successful_count,
        'chunk_index': chunk_index,
        'retry_rounds': retry_count
    }


def generate_student_pdf_with_playwright_simple(student_id, filter_year, search_query, filter_student_id, 
                                               include_graduating_only, display_method, orientation='landscape', 
                                               page_size='A4', base_url='http://localhost:5000'):
    """Simplified thread-safe PDF generation using Playwright with 5-minute timeout"""
    async def generate_student_pdf_async():
        try:
            print(f"DEBUG: Thread-safe generating PDF for student ID: {student_id}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Build URL with filters
                url_params = {'student_id': student_id}
                
                if filter_year:
                    url_params['year'] = filter_year
                if search_query:
                    url_params['search'] = search_query
                if include_graduating_only:
                    url_params['graduating_only'] = 'true'
                
                from urllib.parse import urlencode
                url = f"{base_url}/calculation/all_courses?{urlencode(url_params)}"
                
                # Navigate with 5-minute timeout for complex pages
                await page.goto(url, timeout=300000)  # 5 minutes timeout
                
                # Wait for essential content with extended timeout
                try:
                    await page.wait_for_selector('table', timeout=240000)  # 4 minutes for table
                except:
                    # If table doesn't load, try waiting for any content
                    await page.wait_for_selector('body', timeout=60000)  # 1 minute fallback
                
                # Apply minimal PDF styling
                await page.evaluate(f"""
                    () => {{
                        // Remove only essential interactive elements
                        const elementsToHide = ['.navbar', '.btn', 'button', '.modal', '.dropdown'];
                        elementsToHide.forEach(selector => {{
                            const elements = document.querySelectorAll(selector);
                            elements.forEach(el => el.style.display = 'none');
                        }});
                        
                        // Add basic PDF styles
                        const style = document.createElement('style');
                        style.textContent = `@media print {{ body {{ font-size: 10px; }} .table {{ font-size: 8px; }} }}`;
                        document.head.appendChild(style);
                        
                        // Add title
                        const title = document.createElement('div');
                        title.innerHTML = '<h2 style="text-align: center; margin: 10px 0;">Student Report - ID: {student_id}</h2>';
                        document.body.insertBefore(title, document.body.firstChild);
                    }}
                """)
                
                # Generate PDF with optimized settings
                is_landscape = orientation.lower() == 'landscape'
                margins = {
                    'top': '0.5cm' if page_size.upper() == 'A3' else '0.7cm',
                    'right': '0.5cm' if page_size.upper() == 'A3' else '0.7cm',
                    'bottom': '0.5cm' if page_size.upper() == 'A3' else '0.7cm',
                    'left': '0.5cm' if page_size.upper() == 'A3' else '0.7cm'
                }
                
                pdf_bytes = await page.pdf(
                    format=page_size.upper(),
                    landscape=is_landscape,
                    print_background=True,
                    margin=margins
                )
                
                await browser.close()
                return pdf_bytes
                
        except Exception as e:
            logging.error(f"Error generating PDF for student {student_id}: {e}")
            print(f"DEBUG: PDF generation error for student {student_id}: {e}")
            return None
    
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(generate_student_pdf_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logging.error(f"Error in thread-safe PDF generation for student {student_id}: {e}")
        print(f"DEBUG: Thread-safe PDF generation error for student {student_id}: {e}")
        return None


def combine_pdfs(pdf_paths):
    """Combine multiple PDF files into a single PDF"""
    try:
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        
        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                merger.append(pdf_path)
        
        output_buffer = BytesIO()
        merger.write(output_buffer)
        merger.close()
        
        output_buffer.seek(0)
        return output_buffer.getvalue()
        
    except Exception as e:
        logging.error(f"Error combining PDFs: {e}")
        return None 