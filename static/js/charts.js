// charts.js - Chart handling for ABET results

function setupResultsCharts() {
    console.log('Setting up charts...');
    
    // Make sure Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js library not loaded!');
        document.querySelectorAll('canvas').forEach(canvas => {
            const container = canvas.parentElement;
            const errorMsg = document.createElement('div');
            errorMsg.classList.add('alert', 'alert-danger');
            errorMsg.innerHTML = '<strong>Error:</strong> Chart.js library failed to load. Please check your internet connection and refresh the page.';
            container.insertBefore(errorMsg, canvas);
        });
        return;
    }
    
    try {
        setupProgramOutcomesChart();
        setupCourseOutcomesChart();
        console.log('Charts created successfully');
    } catch (error) {
        console.error('Error creating charts:', error);
        document.querySelectorAll('canvas').forEach(canvas => {
            const container = canvas.parentElement;
            const errorMsg = document.createElement('div');
            errorMsg.classList.add('alert', 'alert-danger');
            errorMsg.innerHTML = `<strong>Error:</strong> Failed to create charts: ${error.message}`;
            container.insertBefore(errorMsg, canvas);
        });
    }
}

function setupProgramOutcomesChart() {
    const canvas = document.getElementById('programOutcomesChart');
    if (!canvas) {
        console.error('Program outcomes chart canvas not found');
        return;
    }
    
    // Get data from data attributes
    const labels = JSON.parse(canvas.getAttribute('data-labels') || '[]');
    const values = JSON.parse(canvas.getAttribute('data-values') || '[]');
    const colors = JSON.parse(canvas.getAttribute('data-colors') || '[]');
    const borderColors = JSON.parse(canvas.getAttribute('data-border-colors') || '[]');
    
    console.log('Program Outcomes data:', { labels, values });
    
    // Create chart
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Achievement Level (%)',
                data: values,
                backgroundColor: colors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Achievement Level (%)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Program Outcomes'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Program Outcome Achievement Levels',
                    font: { size: 16 }
                }
            }
        }
    });
}

function setupCourseOutcomesChart() {
    const canvas = document.getElementById('courseOutcomesChart');
    if (!canvas) {
        console.error('Course outcomes chart canvas not found');
        return;
    }
    
    // Get data from data attributes
    const labels = JSON.parse(canvas.getAttribute('data-labels') || '[]');
    const values = JSON.parse(canvas.getAttribute('data-values') || '[]');
    const colors = JSON.parse(canvas.getAttribute('data-colors') || '[]');
    const borderColors = JSON.parse(canvas.getAttribute('data-border-colors') || '[]');
    
    console.log('Course Outcomes data:', { labels, values });
    
    // Create chart
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Achievement Level (%)',
                data: values,
                backgroundColor: colors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Achievement Level (%)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Course Outcomes'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Course Outcome Achievement Levels',
                    font: { size: 16 }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, charts.js running');
    if (document.getElementById('programOutcomesChart') || document.getElementById('courseOutcomesChart')) {
        setupResultsCharts();
    }
}); 