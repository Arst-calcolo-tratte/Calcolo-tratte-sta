// Set this to your deployed FastAPI backend URL, e.g. https://your-service.example.com
const API_BASE = "http://localhost:8000";
const form = document.querySelector("#convert-form");
const formatCards = [...document.querySelectorAll(".format-card")];
const formatInputs = [...document.querySelectorAll('input[name="format"]')];
const clipMode = document.querySelector("#clip-mode");
const audioMode = document.querySelector("#audio-mode");
const videoOptions = document.querySelector("#video-options");
const gifOptions = document.querySelector("#gif-options");
const audioOptions = document.querySelector("#audio-options");
const clipFields = document.querySelector("#clip-fields");
const statusPanel = document.querySelector("#status-panel");
const statusTitle = document.querySelector("#status-title");
const statusMessage = document.querySelector("#status-message");
const progressBar = document.querySelector("#progress-bar");
const progressPercent = document.querySelector("#status-percent");
const spinner = document.querySelector("#spinner");
const downloadLink = document.querySelector("#download-link");
const convertButton = document.querySelector("#convert-btn");

function selectedFormat(){ return formatInputs.find(x => x.checked)?.value || "mp4"; }
function updateFormat(){
  const fmt = selectedFormat();
  formatCards.forEach(card => card.classList.toggle("selected", card.querySelector("input").checked));
  videoOptions.classList.toggle("hidden", fmt !== "mp4");
  gifOptions.classList.toggle("hidden", fmt !== "gif");
  audioOptions.classList.toggle("hidden", fmt !== "mp3");
  updateClipFields();
}
function updateClipFields(){
  const fmt = selectedFormat();
  const enabled = fmt === "mp4" ? clipMode.value === "clip" : fmt === "mp3" ? audioMode.value === "clip" : false;
  clipFields.classList.toggle("hidden", !enabled);
}
formatInputs.forEach(input => input.addEventListener("change", updateFormat));
clipMode.addEventListener("change", updateClipFields);
audioMode.addEventListener("change", updateClipFields);
updateFormat();

document.querySelector("#paste-btn").addEventListener("click", async () => {
  try {
    document.querySelector("#video-url").value = await navigator.clipboard.readText();
  } catch {
    document.querySelector("#video-url").focus();
    statusPanel.classList.remove("hidden");
    setStatus("Incolla il link", "Il browser non consente l'accesso automatico agli appunti. Incolla il link nel campo qui sopra.", 0);
  }
});

function setStatus(title, message, percent){
  statusPanel.classList.remove("hidden");
  statusTitle.textContent = title;
  statusMessage.textContent = message;
  progressBar.style.width = percent + "%";
  progressPercent.textContent = percent ? percent + "%" : "";
}

function getOptions(){
  const fmt = selectedFormat();
  const mode = fmt === "mp4" ? clipMode.value : fmt === "mp3" ? audioMode.value : "full";
  const options = {
    url: document.querySelector("#video-url").value.trim(),
    format: fmt,
    start: mode === "clip" ? Number(document.querySelector("#clip-start").value || 0) : null,
    end: mode === "clip" ? Number(document.querySelector("#clip-end").value) : null
  };
  if(fmt === "mp4") options.quality = document.querySelector("#quality").value;
  if(fmt === "gif"){
    options.duration = Number(document.querySelector("#gif-duration").value);
    options.width = Number(document.querySelector("#gif-size").value);
  }
  if(fmt === "mp3") options.audio_bitrate = Number(document.querySelector("#audio-quality").value);
  return options;
}

async function pollJob(jobId){
  for(let i=0;i<600;i++){
    await new Promise(resolve => setTimeout(resolve, 2000));
    const response = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`);
    const data = await response.json();
    if(!response.ok) throw new Error(data.detail || "Errore durante il controllo del processo.");
    const percent = Math.max(5, Math.min(100, Number(data.progress || 0)));
    setStatus(data.status === "done" ? "Conversione completata" : data.status === "error" ? "Conversione non riuscita" : "Elaborazione in corso", data.message || "Il server sta elaborando il file.", percent);
    if(data.status === "done"){
      spinner.classList.add("done");
      downloadLink.href = `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/download`;
      downloadLink.download = data.filename || "socialclip-output";
      downloadLink.classList.remove("hidden");
      return;
    }
    if(data.status === "error") throw new Error(data.message || "Elaborazione non riuscita.");
  }
  throw new Error("Tempo massimo di elaborazione superato.");
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if(!form.reportValidity()) return;
  const opts = getOptions();
  if(opts.start !== null && (!Number.isFinite(opts.end) || opts.end <= opts.start)){
    setStatus("Intervallo non valido", "Il tempo finale deve essere maggiore del tempo iniziale.", 0);
    return;
  }
  convertButton.disabled = true;
  downloadLink.classList.add("hidden");
  spinner.classList.remove("done");
  setStatus("Invio richiesta…", "Verifica del link e avvio dell'elaborazione.", 5);
  try{
    const response = await fetch(`${API_BASE}/api/convert`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(opts)
    });
    const data = await response.json();
    if(!response.ok) throw new Error(data.detail || "Impossibile avviare la conversione.");
    setStatus("Richiesta ricevuta", "Il server ha avviato il processo.", 8);
    await pollJob(data.job_id);
  }catch(error){
    spinner.classList.remove("done");
    setStatus("Operazione non riuscita", error.message + " Controlla che il backend sia online e che il link sia supportato.", 0);
  }finally{
    convertButton.disabled = false;
  }
});