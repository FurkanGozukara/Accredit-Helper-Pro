// Main JavaScript for ABET Calculator

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
        const score = parseFloat(input.value) || 0;
        const maxScore = parseFloat(input.getAttribute('data-max-score')) || 0;
        
        total += score;
        maxTotal += maxScore;
    });
    
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