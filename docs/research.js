const $=id=>document.getElementById(id);
for(const button of document.querySelectorAll('[data-results]'))button.addEventListener('click',()=>{
  $('controlled-results').hidden=button.dataset.results!=='controlled';
  $('broader-results').hidden=button.dataset.results!=='broader';
  for(const item of document.querySelectorAll('[data-results]')){item.classList.toggle('selected',item===button);item.setAttribute('aria-pressed',String(item===button));}
});
function filterRows(){
  let count=0;
  for(const row of document.querySelectorAll('#ablation-table tbody tr')){
    row.hidden=($('source-filter').value!=='All sources'&&row.dataset.source!==$('source-filter').value)||($('weight-filter').value!=='All weights'&&row.dataset.weighted!==$('weight-filter').value);
    if(!row.hidden)count++;
  }
  $('row-count').textContent=`${count} condition${count===1?'':'s'}`;
}
$('source-filter').addEventListener('change',filterRows);$('weight-filter').addEventListener('change',filterRows);
$('reset-filters').addEventListener('click',()=>{$('source-filter').selectedIndex=0;$('weight-filter').selectedIndex=0;filterRows();});
const dialog=$('figure-dialog');
for(const button of document.querySelectorAll('[data-figure]'))button.addEventListener('click',()=>{
  $('figure-title').textContent=button.dataset.title;$('enlarged-figure').src=button.dataset.figure;
  $('enlarged-figure').alt=button.closest('figure').querySelector('figcaption').textContent;
  $('figure-download').href=button.dataset.figure;dialog.showModal();
});
$('close-figure').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
$('copy-citation').addEventListener('click',async function(){
  try{await navigator.clipboard.writeText($('bibtex').innerText);this.textContent='Copied ✓';setTimeout(()=>this.textContent='Copy BibTeX ⧉',2000);}
  catch{this.textContent='Select the citation below to copy';}
});
if('IntersectionObserver' in window){
  const observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting)for(const link of document.querySelectorAll('nav a')){
    const active=link.hash==='#'+entry.target.id;link.classList.toggle('active',active);
    if(active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');
  }},{rootMargin:'-10% 0px -65% 0px'});
  for(const section of document.querySelectorAll('main section[id]'))observer.observe(section);
}
