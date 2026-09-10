(function () {
'use strict';

const intel=document.querySelector('#workspace-intel');
const intelContent=document.querySelector('#workspace-intel-content');
if(!intel||!intelContent)return;

const style=document.createElement('style');
style.textContent=`
.workspace-intel.disclosure-collapsed>#workspace-intel-content{display:none}
.intel-head,.cluster-head,.intel-warning>.intel-subtitle,.intel-section>.intel-subtitle{cursor:pointer;user-select:none}
.intel-head::before,.cluster-head::before,.intel-warning>.intel-subtitle::before,.intel-section>.intel-subtitle::before{content:'›';display:inline-block;margin-right:7px;color:#8d9aaf;transition:transform .16s ease}
.workspace-intel:not(.disclosure-collapsed)>.intel-head::before,.cluster-card:not(.disclosure-collapsed)>.cluster-head::before,.intel-warning:not(.disclosure-collapsed)>.intel-subtitle::before,.intel-section:not(.disclosure-collapsed)>.intel-subtitle::before{transform:rotate(90deg)}
.cluster-card.disclosure-collapsed>:not(.cluster-head),.intel-warning.disclosure-collapsed>:not(.intel-subtitle),.intel-section.disclosure-collapsed>:not(.intel-subtitle){display:none}
`;
document.head.appendChild(style);

function setCollapsed(node,collapsed){
  node.classList.toggle('disclosure-collapsed',collapsed);
  node.setAttribute('aria-expanded',collapsed?'false':'true');
}

function wireToggle(node,handle){
  if(!node||!handle||node.dataset.disclosureWired==='1')return;
  node.dataset.disclosureWired='1';
  setCollapsed(node,true);
  handle.setAttribute('role','button');
  handle.setAttribute('tabindex','0');
  const toggle=event=>{
    if(event.target.closest('button,a,input,textarea,select'))return;
    setCollapsed(node,!node.classList.contains('disclosure-collapsed'));
  };
  handle.addEventListener('click',toggle);
  handle.addEventListener('keydown',event=>{
    if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle(event);}
  });
}

function wireNested(){
  intelContent.querySelectorAll('.cluster-card').forEach(node=>wireToggle(node,node.querySelector(':scope > .cluster-head')));
  intelContent.querySelectorAll('.intel-warning').forEach(node=>wireToggle(node,node.querySelector(':scope > .intel-subtitle')));
  intelContent.querySelectorAll('.intel-section').forEach(node=>wireToggle(node,node.querySelector(':scope > .intel-subtitle')));
}

wireToggle(intel,intel.querySelector(':scope > .intel-head'));
const contentObserver=new MutationObserver(wireNested);
contentObserver.observe(intelContent,{childList:true,subtree:true});
wireNested();

const visibilityObserver=new MutationObserver(()=>{
  if(intel.classList.contains('hidden'))setCollapsed(intel,true);
});
visibilityObserver.observe(intel,{attributes:true,attributeFilter:['class']});
})();
