"""Real-weight CPU smoke benchmark on bundled colonoscopy + DICOM examples."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gazerefine.interactive import CPUInference, AppConfig, load_image, read_fixations


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', default=None)
    parser.add_argument('--resolution',type=int,choices=[384,592,1184],default=384)
    parser.add_argument('--output',default='release/benchmark-output')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    engine=CPUInference();results=[]
    for modality,filename,csv in [('colonoscopy','cju0roawvklrq0799vmjorwfv.jpg','kvasir_samples.csv'),
                                  ('mri','Prostate3T-01-0002_16.dcm','nci-isbi_samples.csv')]:
        path=root/'examples/images'/filename;image=load_image(path)
        fix=read_fixations(root/'examples/fixations'/csv,*image.size,image_name=filename)
        r=engine.predict(image,fix,AppConfig(modality=modality,resolution=args.resolution,checkpoint=args.checkpoint))
        assert r['mask'].size==image.size
        for key in ['mask','overlay','prior']:r[key].save(out/f'{modality}_{key}.png')
        results.append(r['metadata']);print(json.dumps(r['metadata']),flush=True)
    (out/'benchmark.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
