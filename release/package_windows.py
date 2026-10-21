from pathlib import Path
import json,shutil,zipfile,hashlib
r=Path('.').resolve();dest=r/'dist/GazeRefine'
shutil.copyfile(r/'release/PORTABLE_README.txt',dest/'READ_ME_FIRST.txt')
meta=json.loads((r/'release/benchmark-output/frozen-exe-v2/result.json').read_text());meta.pop('checkpoint',None)
(r/'release/cpu-frozen-exe-benchmark.json').write_text(json.dumps(meta,indent=2))
# Omit dependency demo datasets; they are not needed to decode user images.
archive=r/'release/GazeRefine-Windows-CPU-preview.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in dest.rglob('*'):
  if not f.is_file():continue
  relative=f.relative_to(dest).as_posix()
  if any(part in relative for part in ['pydicom/data/test_files/','pydicom/data/charset_files/','pydicom/data/palettes/','matplotlib/mpl-data/sample_data/']):continue
  assert not any(suffix in f.name.lower() for suffix in ['.safetensors','.dcm','.dicom']),relative
  z.write(f,'GazeRefine/'+relative)
with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else None
if digest is None:
 h=hashlib.sha256()
 with archive.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 digest=h.hexdigest()
(r/'release/SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n')
print(json.dumps({'zip':archive.name,'bytes':archive.stat().st_size,'sha256':digest}))
