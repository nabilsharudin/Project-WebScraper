document.querySelectorAll('.edit-trigger').forEach((button) => {
  button.addEventListener('click', () => {
    const row = document.getElementById(button.dataset.target);
    row.hidden = !row.hidden;
  });
});

document.querySelectorAll('.loading-form').forEach((form) => {
  form.addEventListener('submit', () => {
    document.querySelector('.loading-overlay').hidden = false;
  });
});

const importForm = document.querySelector('.import-form');
const overlay = document.querySelector('.loading-overlay');
const progressBar = document.querySelector('.progress-bar');
const progressPercent = document.querySelector('.progress-percent');
const loadingPhase = document.querySelector('.loading-phase');
const loadingDetail = document.querySelector('.loading-detail');

function showProgress(job) {
  const percent = Math.max(0, Math.min(100, Number(job.percent) || 0));
  progressBar.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;
  loadingPhase.textContent = job.phase || 'Working with the directory…';
  loadingDetail.textContent = job.total
    ? `${job.current} of ${job.total} in this stage · requests are intentionally spaced apart`
    : 'Please keep this tab open.';
}

async function pollImport(jobId) {
  try {
    const response = await fetch(`/imports/${jobId}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Progress information is unavailable.');
    const job = await response.json();
    showProgress(job);
    if (job.status === 'completed') {
      window.location.href = `/?message=${encodeURIComponent(job.message)}&kind=success`;
      return;
    }
    if (job.status === 'failed') {
      window.location.href = `/?message=${encodeURIComponent(job.message)}&kind=error`;
      return;
    }
    window.setTimeout(() => pollImport(jobId), 650);
  } catch (error) {
    loadingPhase.textContent = 'Could not read import progress';
    loadingDetail.textContent = error.message;
  }
}

if (importForm) {
  importForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    overlay.hidden = false;
    showProgress({ percent: 0, phase: 'Starting a gentle import…' });
    try {
      const response = await fetch(importForm.action, {
        method: 'POST',
        body: new FormData(importForm),
      });
      if (!response.ok) throw new Error('The import could not be started.');
      const data = await response.json();
      pollImport(data.job_id);
    } catch (error) {
      loadingPhase.textContent = 'Import could not start';
      loadingDetail.textContent = error.message;
    }
  });
}

const alert = document.querySelector('.alert');
if (alert) window.setTimeout(() => alert.remove(), 5000);
