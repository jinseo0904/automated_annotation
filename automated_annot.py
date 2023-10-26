import os
import sys
import whisperx
import gc 
import string
import pandas as pd
import argparse
# from dask.distributed import print


def run_whisperx(in_dir, out_dir, use_gpu=False, smokescreen=False):
    # if smokescreen:
    #     from dask.distributed import print
    print('starting run_whisperx with')
    print(in_dir, out_dir)
    # Check if the provided directory path exists
    if not os.path.exists(in_dir):
        print(f"The input directory {in_dir} does not exist.")
        sys.exit(1)

    # Check if the provided path is a directory
    if not os.path.isdir(in_dir):
        print(f"The input path {in_dir} is not a directory.")
        sys.exit(1)

    device = "cuda:0" if use_gpu else "cpu"
    print("\n\n====== Device type : {} ======".format(device))
    batch_size = 16 # reduce if low on GPU mem
    compute_type = "float16" if use_gpu else "int8"
    model_size = "large-v2" if not smokescreen else 'tiny.en'
    model = whisperx.load_model(model_size, device, compute_type=compute_type)
    
    # create a subdirectory to store all results
    assert out_dir != in_dir
    out_dir = os.path.join(out_dir, 'whisperx_out')
    os.makedirs(out_dir, exist_ok=True)

    # List all .wav files in the directory
    wav_files = [f for f in os.listdir(in_dir) if f.endswith('.wav')]
    if smokescreen: wav_files = wav_files[:1]

    # Print the .wav files
    if wav_files:
        print("WAV files found:")
        for file in wav_files:
            print("\n\nProcessing {}...".format(file))
            
            # define audio file
            filepath = os.path.join(in_dir, file)
            print('loading audio', filepath)
            audio = whisperx.load_audio(filepath)
            if smokescreen:
                audio = audio[:len(audio) // 3]
            print('loaded audio')
            result = model.transcribe(audio, batch_size=batch_size)
            #print(result["segments"]) # before alignment
            
            # delete model if low on GPU resources
            # import gc; gc.collect(); torch.cuda.empty_cache(); del model
            
            # 2. Align whisper output
            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            
            #print(result["segments"]) # after alignment
            
            # delete model if low on GPU resources
            # import gc; gc.collect(); torch.cuda.empty_cache(); del model_a

            words, onsets, offsets, confidence = [], [], [], []
            
            for segment in result["segments"]:
            
                word_list = segment['words']
                for element in word_list:
                    #print(element)
                    word = element['word']
                    onset_time = element['start']
                    offset_time = element['end']
                    prob = element['score']
                
                    newword = word.translate(str.maketrans('', '', string.punctuation)).upper()
                    words.append(newword)
                    onsets.append(int(onset_time * 1000))
                    offsets.append(int(offset_time * 1000))
                    confidence.append(prob)
                    #print(newword, int(onset_time * 1000), prob)

            # Create a DataFrame from the three lists
            df = pd.DataFrame({'Word': words, 'Onset': onsets, 'Offset': offsets, 'Probability': confidence})
            
            # Print the DataFrame (optional, for verification)
            #print(df)
            
            # Save the DataFrame to a CSV file
            output_name = os.path.splitext(file)[0] + ".csv"
            savepath = os.path.join(out_dir, output_name)
            df.to_csv(savepath, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automated Speech Annotation using AI Models')
    parser.add_argument('--input_dir', type=str, required=True, help='Path to the input directory.')
    parser.add_argument('--output_dir', type=str, required=True, help='Path to the input directory.')
    parser.add_argument('--use_gpu', action='store_true', default=False, help='Flag to use GPU.')
    # Parse the arguments
    args = parser.parse_args()

    # Now, you can access the input directory using args.input_dir
    print("Input Directory:", args.input_dir)

    # Check if the provided directory path exists
    if not os.path.exists(args.input_dir):
        print(f"The directory {args.input_dir} does not exist.")
        sys.exit(1)

    # Check if the provided path is a directory
    if not os.path.isdir(args.input_dir):
        print(f"The path {args.input_dir} is not a directory.")
        sys.exit(1)

    # default: Run whisperX only
    run_whisperx(args.input_dir, args.output_dir, args.use_gpu)