const toggle=document.getElementById('toggle-demo');
toggle.addEventListener('click',()=>{
  const overlay=toggle.getAttribute('aria-pressed')!=='true';
  document.getElementById('demo-image').src=overlay?'https://raw.githubusercontent.com/MohammedOussamaBEN/GazeRefine/main/img/seg_results.png':'https://raw.githubusercontent.com/MohammedOussamaBEN/GazeRefine/main/img/zero-shot_archi.jpg';
  document.getElementById('demo-label').textContent=overlay?'Published segmentation results':'Method overview';
  toggle.textContent=overlay?'Show pipeline ↔':'Show results ↔';toggle.setAttribute('aria-pressed',String(overlay));
});
document.getElementById('copy-citation').addEventListener('click',async function(){
  try{await navigator.clipboard.writeText(document.getElementById('bibtex').innerText);this.textContent='Copied ✓';setTimeout(()=>this.textContent='Copy BibTeX ⧉',2000);}
  catch{this.textContent='Select the citation below to copy';}
});
