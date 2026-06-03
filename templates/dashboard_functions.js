/**
 * Auto-refresh timer for the serverless job list.
 * Active only when the orchestratorServerless tab is visible.
 */
let serverlessRefreshInterval = null;

/**
 * Start auto-refreshing the serverless job list every 5 seconds.
 * Clears any existing interval before starting a new one.
 */
function startServerlessAutoRefresh() {
    stopServerlessAutoRefresh();
    serverlessRefreshInterval = setInterval(function() {
        refreshJobList();
        loadServerlessMetrics();
    }, 5000);
}

/**
 * Stop the auto-refresh timer for the serverless job list.
 */
function stopServerlessAutoRefresh() {
    if (serverlessRefreshInterval !== null) {
        clearInterval(serverlessRefreshInterval);
        serverlessRefreshInterval = null;
    }
}

/**
 * Submit a serverless Docker job via POST /api/jobs.
 * Reads form inputs, builds the payload, and refreshes the job list on success.
 */
async function submitServerlessJob() {
    const image = document.getElementById('serverlessImage').value.trim();
    const commandStr = document.getElementById('serverlessCommand').value.trim();
    const envStr = document.getElementById('serverlessEnv').value.trim();
    const timeoutStr = document.getElementById('serverlessTimeout').value.trim();

    // Validate required fields
    if (!image) {
        alert('Error: Docker image is required.');
        return;
    }
    if (!commandStr) {
        alert('Error: Command is required.');
        return;
    }

    // Parse command string into array by splitting on spaces
    const command = commandStr.split(/\s+/);

    // Build the request payload
    const payload = {
        image: image,
        command: command
    };

    // Parse environment variables JSON if provided
    if (envStr) {
        try {
            const env = JSON.parse(envStr);
            payload.env = env;
        } catch (e) {
            alert('Error: Environment variables must be valid JSON.\n' + e.message);
            return;
        }
    }

    // Include timeout if provided
    if (timeoutStr) {
        const timeout = parseInt(timeoutStr, 10);
        if (isNaN(timeout) || timeout < 1 || timeout > 3600) {
            alert('Error: Timeout must be between 1 and 3600 seconds.');
            return;
        }
        payload.timeout = timeout;
    }

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            alert('Job submitted successfully! Job ID: ' + data.job_id);
            // Reset the form
            document.getElementById('serverlessJobForm').reset();
            // Refresh the job list
            if (typeof refreshJobList === 'function') {
                refreshJobList();
            }
        } else {
            const errorData = await response.json().catch(() => null);
            const errorMsg = errorData && errorData.error ? errorData.error : 'HTTP ' + response.status;
            alert('Failed to submit job: ' + errorMsg);
        }
    } catch (err) {
        alert('Network error submitting job: ' + err.message);
    }
}

function formatRepoSize(sizeInMB) {
    if (sizeInMB < 10) {
        return `Small (${sizeInMB}MB)`;
    } else if (sizeInMB < 100) {
        return `Medium (${sizeInMB}MB)`;
    } else if (sizeInMB < 1000) {
        return `Large (${sizeInMB}MB)`;
    } else {
        return `Very Large (${(sizeInMB/1000).toFixed(1)}GB)`;
    }
}

function startCloneProgressSimulation(repoSizeMB) {
    let progress = 0;
    let startTime = Date.now();
    
    // Calculate estimated duration based on actual repo size
    let estimatedDuration;
    if (repoSizeMB < 10) {
        estimatedDuration = 15 + (repoSizeMB * 1.5); // 15-30 seconds
    } else if (repoSizeMB < 100) {
        estimatedDuration = 30 + (repoSizeMB * 0.8); // 30-110 seconds
    } else if (repoSizeMB < 1000) {
        estimatedDuration = 120 + (repoSizeMB * 0.3); // 2-7 minutes
    } else {
        estimatedDuration = 300 + (repoSizeMB * 0.1); // 5+ minutes
    }
    
    // Set initial estimated time
    document.getElementById('estimatedTime').textContent = formatDuration(Math.round(estimatedDuration));
    
    const progressInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        document.getElementById('elapsedTime').textContent = elapsed + 's';
        
        // Simulate realistic progress curve (slower at start, faster in middle, slower at end)
        const timeRatio = elapsed / estimatedDuration;
        if (timeRatio < 0.1) {
            progress = timeRatio * 50; // 0-5% in first 10% of time
        } else if (timeRatio < 0.8) {
            progress = 5 + (timeRatio - 0.1) * 128.57; // 5-95% in next 70% of time
        } else {
            progress = 95 + (timeRatio - 0.8) * 25; // 95-100% in last 20% of time
        }
        
        progress = Math.min(progress, 99); // Never reach 100% until actually done
        
        const progressBar = document.getElementById('cloneProgress');
        const progressText = document.getElementById('progressText');
        
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
        
        if (progressText) {
            if (progress < 10) {
                progressText.textContent = 'Connecting to repository...';
            } else if (progress < 30) {
                progressText.textContent = 'Downloading repository metadata...';
            } else if (progress < 70) {
                progressText.textContent = 'Cloning files and history...';
            } else if (progress < 90) {
                progressText.textContent = 'Processing repository structure...';
            } else {
                progressText.textContent = 'Finalizing clone operation...';
            }
        }
        
        // Update estimated time remaining
        const remaining = Math.max(0, estimatedDuration - elapsed);
        if (remaining > 0) {
            document.getElementById('estimatedTime').textContent = formatDuration(remaining) + ' remaining';
        }
        
    }, 1000);
    
    // Store interval ID to clear it later
    window.cloneProgressInterval = progressInterval;
}


/**
 * Refresh the serverless jobs list by fetching from GET /api/jobs
 * and rendering the job table with status badges and action buttons.
 */
async function refreshJobList() {
    const tbody = document.getElementById('serverlessJobsBody');
    if (!tbody) return;

    try {
        const response = await fetch('/api/jobs', {
            method: 'GET',
            credentials: 'same-origin'
        });

        if (!response.ok) {
            tbody.innerHTML = '<tr><td colspan="5">Failed to load jobs (HTTP ' + response.status + ')</td></tr>';
            return;
        }

        const data = await response.json();
        const jobs = data.jobs || [];

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5">No jobs found</td></tr>';
            return;
        }

        let html = '';
        for (const job of jobs) {
            const createdAt = job.created_at ? new Date(job.created_at).toLocaleString() : 'N/A';
            const statusBadge = '<span class="job-status-badge status-' + job.status + '">' + job.status + '</span>';

            let actions = '<button class="btn btn-secondary btn-small" onclick="viewJobDetail(\'' + job.id + '\')">View</button>';
            if (job.status === 'pending' || job.status === 'running') {
                actions += ' <button class="btn btn-danger btn-small" onclick="cancelJob(\'' + job.id + '\')">Cancel</button>';
            }

            html += '<tr>';
            html += '<td>' + job.id + '</td>';
            html += '<td>' + job.image + '</td>';
            html += '<td>' + statusBadge + '</td>';
            html += '<td>' + createdAt + '</td>';
            html += '<td>' + actions + '</td>';
            html += '</tr>';
        }

        tbody.innerHTML = html;
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="5">Network error loading jobs: ' + err.message + '</td></tr>';
    }
}

/**
 * View job detail by fetching job status and result from the API,
 * then displaying the information in the detail panel.
 * @param {string} jobId - The UUID of the job to view
 */
async function viewJobDetail(jobId) {
    const detailPanel = document.getElementById('serverlessJobDetail');
    const detailContent = document.getElementById('serverlessJobDetailContent');

    if (!detailPanel || !detailContent) return;

    // Show the panel and indicate loading
    detailPanel.style.display = 'block';
    detailContent.innerHTML = '<p>Loading job details...</p>';

    try {
        // Fetch job status
        const statusResponse = await fetch('/api/jobs/' + jobId, {
            method: 'GET',
            credentials: 'same-origin'
        });

        if (!statusResponse.ok) {
            const errData = await statusResponse.json().catch(() => null);
            const errMsg = errData && errData.error ? errData.error : 'HTTP ' + statusResponse.status;
            detailContent.innerHTML = '<p style="color:red;">Failed to load job details: ' + errMsg + '</p>';
            return;
        }

        const job = await statusResponse.json();

        // Build job metadata HTML
        let html = '<table class="job-detail-table" style="width:100%; border-collapse:collapse; margin-bottom:15px;">';
        html += '<tr><td><strong>Job ID:</strong></td><td>' + (job.job_id || jobId) + '</td></tr>';
        html += '<tr><td><strong>Status:</strong></td><td><span class="job-status-badge status-' + job.status + '">' + job.status + '</span></td></tr>';
        html += '<tr><td><strong>Image:</strong></td><td>' + (job.image || 'N/A') + '</td></tr>';
        html += '<tr><td><strong>Created:</strong></td><td>' + (job.created_at ? new Date(job.created_at).toLocaleString() : 'N/A') + '</td></tr>';
        html += '<tr><td><strong>Started:</strong></td><td>' + (job.started_at ? new Date(job.started_at).toLocaleString() : 'N/A') + '</td></tr>';
        html += '<tr><td><strong>Completed:</strong></td><td>' + (job.completed_at ? new Date(job.completed_at).toLocaleString() : 'N/A') + '</td></tr>';
        html += '<tr><td><strong>Exit Code:</strong></td><td>' + (job.exit_code !== null && job.exit_code !== undefined ? job.exit_code : 'N/A') + '</td></tr>';
        html += '<tr><td><strong>Worker:</strong></td><td>' + (job.worker_id || 'N/A') + '</td></tr>';
        html += '</table>';

        // If job is in a terminal state, fetch the result
        const terminalStates = ['completed', 'failed', 'timeout', 'cancelled'];
        if (terminalStates.includes(job.status)) {
            try {
                const resultResponse = await fetch('/api/jobs/' + jobId + '/result', {
                    method: 'GET',
                    credentials: 'same-origin'
                });

                if (resultResponse.ok) {
                    const result = await resultResponse.json();

                    html += '<h4 style="margin-top:10px;">Result</h4>';
                    html += '<p><strong>Exit Code:</strong> ' + (result.exit_code !== null && result.exit_code !== undefined ? result.exit_code : 'N/A') + '</p>';

                    if (result.stdout) {
                        html += '<h5>Stdout:</h5>';
                        html += '<pre style="background:#1e1e1e; color:#d4d4d4; padding:10px; border-radius:4px; overflow-x:auto; max-height:300px; overflow-y:auto;">' + escapeHtml(result.stdout) + '</pre>';
                    }

                    if (result.stderr) {
                        html += '<h5>Stderr:</h5>';
                        html += '<pre style="background:#2d1515; color:#f48771; padding:10px; border-radius:4px; overflow-x:auto; max-height:300px; overflow-y:auto;">' + escapeHtml(result.stderr) + '</pre>';
                    }

                    if (result.result && Object.keys(result.result).length > 0) {
                        html += '<h5>Structured Result:</h5>';
                        html += '<pre style="background:#f8f9fa; padding:10px; border-radius:4px; overflow-x:auto;">' + escapeHtml(JSON.stringify(result.result, null, 2)) + '</pre>';
                    }
                } else if (resultResponse.status !== 409) {
                    // 409 means job not in terminal state (shouldn't happen here), other errors we show
                    html += '<p style="color:orange;">Could not load job result (HTTP ' + resultResponse.status + ')</p>';
                }
            } catch (resultErr) {
                html += '<p style="color:orange;">Network error loading result: ' + resultErr.message + '</p>';
            }
        }

        detailContent.innerHTML = html;
    } catch (err) {
        detailContent.innerHTML = '<p style="color:red;">Network error loading job details: ' + err.message + '</p>';
    }
}

/**
 * Cancel a serverless job by POSTing to /api/jobs/{id}/cancel.
 * Shows a confirmation dialog before proceeding.
 * @param {string} jobId - The UUID of the job to cancel
 */
async function cancelJob(jobId) {
    if (!confirm('Are you sure you want to cancel this job?')) {
        return;
    }

    try {
        const response = await fetch('/api/jobs/' + jobId + '/cancel', {
            method: 'POST',
            credentials: 'same-origin'
        });

        if (response.ok) {
            alert('Job cancelled successfully.');
            refreshJobList();
        } else {
            const errorData = await response.json().catch(() => null);
            const errorMsg = errorData && errorData.error ? errorData.error : 'HTTP ' + response.status;
            if (response.status === 409) {
                alert('Cannot cancel job: ' + errorMsg);
            } else {
                alert('Failed to cancel job: ' + errorMsg);
            }
        }
    } catch (err) {
        alert('Network error cancelling job: ' + err.message);
    }
}

/**
 * Load serverless job metrics from GET /api/jobs/metrics (admin-only)
 * and render the metrics panel with styled metric cards.
 */
async function loadServerlessMetrics() {
    const content = document.getElementById('serverlessMetricsContent');
    if (!content) return;

    try {
        const response = await fetch('/api/jobs/metrics', {
            method: 'GET',
            credentials: 'same-origin'
        });

        if (response.status === 403) {
            content.innerHTML = '<p style="color:#666; font-style:italic;">Metrics are available to administrators only.</p>';
            return;
        }

        if (!response.ok) {
            content.innerHTML = '<p style="color:red;">Failed to load metrics (HTTP ' + response.status + ')</p>';
            return;
        }

        const data = await response.json();

        const avgExec = data.avg_execution_time !== null ? data.avg_execution_time + 's' : 'N/A';
        const avgStartup = data.avg_startup_duration !== null ? data.avg_startup_duration + 's' : 'N/A';

        let html = '<div style="display:flex; flex-wrap:wrap; gap:15px;">';

        html += '<div style="flex:1; min-width:120px; padding:12px; background:#fff; border-radius:6px; border:1px solid #e0e0e0; text-align:center;">';
        html += '<div style="font-size:24px; font-weight:bold; color:#6c757d;">' + data.pending_count + '</div>';
        html += '<div style="font-size:12px; color:#888;">Pending</div>';
        html += '</div>';

        html += '<div style="flex:1; min-width:120px; padding:12px; background:#fff; border-radius:6px; border:1px solid #e0e0e0; text-align:center;">';
        html += '<div style="font-size:24px; font-weight:bold; color:#007bff;">' + data.running_count + '</div>';
        html += '<div style="font-size:12px; color:#888;">Running</div>';
        html += '</div>';

        html += '<div style="flex:1; min-width:120px; padding:12px; background:#fff; border-radius:6px; border:1px solid #e0e0e0; text-align:center;">';
        html += '<div style="font-size:24px; font-weight:bold; color:#dc3545;">' + data.failed_count + '</div>';
        html += '<div style="font-size:12px; color:#888;">Failed</div>';
        html += '</div>';

        html += '<div style="flex:1; min-width:120px; padding:12px; background:#fff; border-radius:6px; border:1px solid #e0e0e0; text-align:center;">';
        html += '<div style="font-size:24px; font-weight:bold; color:#28a745;">' + avgExec + '</div>';
        html += '<div style="font-size:12px; color:#888;">Avg Execution</div>';
        html += '</div>';

        html += '<div style="flex:1; min-width:120px; padding:12px; background:#fff; border-radius:6px; border:1px solid #e0e0e0; text-align:center;">';
        html += '<div style="font-size:24px; font-weight:bold; color:#6c757d;">' + data.queue_depth + '</div>';
        html += '<div style="font-size:12px; color:#888;">Queue Depth</div>';
        html += '</div>';

        html += '<div style="flex:1; min-width:120px; padding:12px; background:#fff; border-radius:6px; border:1px solid #e0e0e0; text-align:center;">';
        html += '<div style="font-size:24px; font-weight:bold; color:#17a2b8;">' + avgStartup + '</div>';
        html += '<div style="font-size:12px; color:#888;">Avg Startup</div>';
        html += '</div>';

        html += '</div>';

        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = '<p style="color:red;">Network error loading metrics: ' + err.message + '</p>';
    }
}

/**
 * Escape HTML special characters to prevent XSS when displaying user content.
 * @param {string} text - The text to escape
 * @returns {string} The escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
