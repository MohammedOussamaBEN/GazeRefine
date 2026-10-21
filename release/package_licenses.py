from pathlib import Path
import shutil,importlib.metadata,re
root=Path('.').resolve();dest=root/'dist/GazeRefine'
for name in ['LICENSE','THIRD_PARTY.md','APP_GUIDE.md']:
 shutil.copyfile(root/name,dest/name)
licenses=dest/'THIRD_PARTY_LICENSES';licenses.mkdir(exist_ok=True)
site=root/'.venv-build/Lib/site-packages'
count=0
for dist in importlib.metadata.distributions(path=[str(site)]):
 name=re.sub(r'[^a-zA-Z0-9_.-]','_',dist.metadata['Name'])
 for file in dist.files or []:
  f=Path(str(file));base=f.name.lower()
  if not (base.startswith(('license','copying','notice','copyright')) and f.suffix.lower() in ['','.txt','.md','.rst']):continue
  source=Path(dist.locate_file(file)).resolve()
  if source.is_file() and source.is_relative_to(site.resolve()):
   target=licenses/name/str(f).replace('..','_').replace('/','_').replace('\\','_');target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(source,target);count+=1
print('Copied',count,'dependency license/notice files.')
