"""Entry point used by source launchers and PyInstaller."""
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import sys
    if "--smoke-test" in sys.argv:
        import argparse
        import json
        from pathlib import Path
        from gazerefine.interactive import AppConfig, CPUInference, load_image, read_fixations
        parser=argparse.ArgumentParser()
        parser.add_argument('--smoke-test',action='store_true')
        parser.add_argument('--image',required=True)
        parser.add_argument('--fixations',required=True)
        parser.add_argument('--checkpoint')
        parser.add_argument('--output',required=True)
        args=parser.parse_args()
        image=load_image(args.image)
        fix=read_fixations(args.fixations,*image.size,image_name=Path(args.image).name)
        result=CPUInference().predict(image,fix,AppConfig(checkpoint=args.checkpoint))
        output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
        result['mask'].save(output/'mask.png')
        (output/'result.json').write_text(json.dumps(result['metadata'],indent=2))
    else:
        from desktop.app import main
        main()
