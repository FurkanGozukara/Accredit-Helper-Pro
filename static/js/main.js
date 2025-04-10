// Main JavaScript for Accredit Helper Pro

document.addEventListener('DOMContentLoaded', function() {
    // Initialize delete confirmation modal
    initDeleteConfirmation();
    
    // Initialize auto-save for score inputs
    initScoreAutoSave();
    
    // Initialize any tooltips
    initTooltips();
    
    // Setup global AJAX error handler
    setupGlobalErrorHandler();
});

// Setup global error handling for AJAX requests
function setupGlobalErrorHandler() {
    // Override the fetch API with custom error handling
    const originalFetch = window.fetch;
    window.fetch = function() {
        return originalFetch.apply(this, arguments)
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        try {
                            // Try to parse as JSON first
                            const data = JSON.parse(text);
                            if (data.error) {
                                displayErrorModal('Error', data.error, data.traceback || null);
                                throw new Error(data.error);
                            }
                        } catch (e) {
                            // If not JSON or no error field, display the raw error
                            displayErrorModal('Server Error', text);
                            throw new Error('Server error: ' + response.status);
                        }
                    });
                }
                return response;
            })
            .catch(error => {
                console.error('Fetch error:', error);
                // Display error if it wasn't already displayed above
                if (!error.message.includes('Server error:') && !error.message.startsWith('Error:')) {
                    displayErrorModal('Network Error', error.message);
                }
                throw error;
            });
    };
    
    // Add error modal to the DOM if it doesn't exist
    if (!document.getElementById('errorDetailsModal')) {
        const modalHTML = `
        <div class="modal fade" id="errorDetailsModal" tabindex="-1" aria-labelledby="errorDetailsModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-danger text-white">
                        <h5 class="modal-title" id="errorDetailsModalLabel">Error Details</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <h4 id="errorTitle">Error</h4>
                        <div class="alert alert-danger" id="errorMessage"></div>
                        <div id="errorTracebackContainer" class="mt-3">
                            <h5>Technical Details:</h5>
                            <pre class="bg-light p-3"><code id="errorTraceback"></code></pre>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>`;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
}

// Display error details in modal
function displayErrorModal(title, message, traceback = null) {
    const modal = document.getElementById('errorDetailsModal');
    if (!modal) return;
    
    document.getElementById('errorTitle').textContent = title;
    document.getElementById('errorMessage').textContent = message;
    
    const tracebackContainer = document.getElementById('errorTracebackContainer');
    const tracebackElement = document.getElementById('errorTraceback');
    
    if (traceback) {
        tracebackElement.textContent = traceback;
        tracebackContainer.style.display = 'block';
    } else {
        tracebackContainer.style.display = 'none';
    }
    
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// Handle delete confirmation modal
function initDeleteConfirmation() {
    // Get the modal
    const confirmDeleteModal = document.getElementById('confirmDeleteModal');
    
    if (!confirmDeleteModal) return;
    
    // Find all delete buttons with data-* attributes
    const deleteButtons = document.querySelectorAll('[data-delete-url]');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get data attributes
            const url = this.getAttribute('data-delete-url');
            const name = this.getAttribute('data-delete-name') || 'this item';
            
            // Set the item name in the modal
            document.getElementById('deleteItemName').textContent = name;
            
            // Set the form action
            document.getElementById('deleteForm').action = url;
            
            // Show the modal
            const modal = new bootstrap.Modal(confirmDeleteModal);
            modal.show();
        });
    });
}

// Auto-save score inputs
function initScoreAutoSave() {
    const scoreInputs = document.querySelectorAll('.score-input');
    
    if (scoreInputs.length === 0) return;
    
    scoreInputs.forEach(input => {
        let saveTimeout;
        
        // Add change and keyup event listeners
        input.addEventListener('input', function() {
            clearTimeout(saveTimeout);
            
            // Validate score against max value
            const maxScore = parseFloat(this.getAttribute('data-max-score'));
            let scoreValue = parseFloat(this.value);
            
            if (!isNaN(scoreValue)) {
                if (scoreValue > maxScore) {
                    scoreValue = maxScore;
                    this.value = maxScore;
                }
                this.value = parseFloat(scoreValue.toFixed(1));
            }
            
            const studentId = this.getAttribute('data-student-id');
            const questionId = this.getAttribute('data-question-id');
            const examId = this.getAttribute('data-exam-id');
            const indicator = document.querySelector(`#save-indicator-${studentId}-${questionId}`);
            
            if (indicator) {
                indicator.textContent = 'Saving...';
                indicator.classList.remove('autosave-error');
                indicator.style.display = 'inline';
            }
            
            // Debounce the save
            saveTimeout = setTimeout(() => {
                saveScore(this.value, studentId, questionId, examId, indicator);
            }, 800);
        });
    });
}

// Save score via AJAX
function saveScore(score, studentId, questionId, examId, indicator) {
    const data = {
        student_id: studentId,
        question_id: questionId,
        score: score
    };
    
    fetch(`/student/exam/${examId}/scores/auto-save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (indicator) {
            if (data.success) {
                indicator.textContent = 'Saved';
                
                // Hide indicator after 2 seconds
                setTimeout(() => {
                    indicator.style.display = 'none';
                }, 2000);
            } else {
                indicator.textContent = data.message || 'Error saving';
                indicator.classList.add('autosave-error');
            }
        }
    })
    .catch(error => {
        if (indicator) {
            indicator.textContent = 'Error saving';
            indicator.classList.add('autosave-error');
        }
        console.error('Error saving score:', error);
    });
}

// Initialize Bootstrap tooltips
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Calculate total score for student
function calculateStudentTotal(studentId, examId) {
    const scoreInputs = document.querySelectorAll(`.score-input[data-student-id="${studentId}"][data-exam-id="${examId}"]`);
    let total = 0;
    let maxTotal = 0;
    
    scoreInputs.forEach(input => {
        const value = parseFloat(input.value) || 0;
        const maxScore = parseFloat(input.getAttribute('data-max-score')) || 0;
        
        total += value;
        maxTotal += maxScore;
    });
    
    total = parseFloat(total.toFixed(2));
    maxTotal = parseFloat(maxTotal.toFixed(2));
    
    const totalElement = document.getElementById(`total-${studentId}`);
    if (totalElement) {
        totalElement.textContent = `${total.toFixed(1)} / ${maxTotal.toFixed(1)}`;
        
        // Calculate percentage
        const percentage = maxTotal > 0 ? (total / maxTotal) * 100 : 0;
        totalElement.setAttribute('data-percentage', percentage.toFixed(1));
        
        // Update color based on percentage
        if (percentage >= 70) {
            totalElement.classList.add('text-success');
            totalElement.classList.remove('text-warning', 'text-danger');
        } else if (percentage >= 40) {
            totalElement.classList.add('text-warning');
            totalElement.classList.remove('text-success', 'text-danger');
        } else {
            totalElement.classList.add('text-danger');
            totalElement.classList.remove('text-success', 'text-warning');
        }
    }
}

// Helper function to navigate to all courses calculation
function navigateToAllCoursesCalculation() {
    // Navigate directly to the all_courses page
    window.location.href = '/calculation/all_courses';
} 