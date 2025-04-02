// Main JavaScript for Accredit Helper Pro

document.addEventListener('DOMContentLoaded', function() {
    // Initialize delete confirmation modal
    initDeleteConfirmation();
    
    // Initialize auto-save for score inputs
    initScoreAutoSave();
    
    // Initialize any tooltips
    initTooltips();
});

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

// Helper function to navigate to all courses calculation with loading state
function navigateToAllCoursesCalculation() {
    // Create a full-screen loading overlay
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = 0;
    overlay.style.left = 0;
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.backgroundColor = 'rgba(255,255,255,0.9)';
    overlay.style.zIndex = 9999;
    overlay.style.display = 'flex';
    overlay.style.flexDirection = 'column';
    overlay.style.justifyContent = 'center';
    overlay.style.alignItems = 'center';
    
    // Loading spinner
    const spinner = document.createElement('div');
    spinner.className = 'spinner-border text-primary mb-3';
    spinner.style.width = '3rem';
    spinner.style.height = '3rem';
    spinner.setAttribute('role', 'status');
    
    const spinnerText = document.createElement('span');
    spinnerText.className = 'visually-hidden';
    spinnerText.textContent = 'Loading...';
    spinner.appendChild(spinnerText);
    
    // Loading text
    const loadingText = document.createElement('h4');
    loadingText.className = 'mb-3';
    loadingText.textContent = 'Navigating to calculations...';
    
    // Progress bar container
    const progressContainer = document.createElement('div');
    progressContainer.className = 'progress mt-4';
    progressContainer.style.height = '20px';
    progressContainer.style.width = '60%';
    
    // Progress bar
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
    progressBar.setAttribute('role', 'progressbar');
    progressBar.style.width = '0%';
    progressBar.setAttribute('aria-valuenow', '0');
    progressBar.setAttribute('aria-valuemin', '0');
    progressBar.setAttribute('aria-valuemax', '100');
    progressBar.textContent = '0%';
    
    progressContainer.appendChild(progressBar);
    
    // Add elements to overlay
    overlay.appendChild(spinner);
    overlay.appendChild(loadingText);
    overlay.appendChild(progressContainer);
    
    // Add overlay to body
    document.body.appendChild(overlay);
    
    // Animate progress bar
    let progress = 0;
    const progressInterval = setInterval(() => {
        // Increment progress, slowing down as it approaches 90%
        const increment = Math.max(1, 10 - Math.floor(progress / 10));
        progress = Math.min(90, progress + increment);
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        progressBar.textContent = `${progress}%`;
    }, 300);
    
    // Navigate to the calculation page
    window.location.href = '/calculation/all_courses_loading';
} 