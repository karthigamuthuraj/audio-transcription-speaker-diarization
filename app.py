import streamlit as st
import whisper
from pyannote.audio import Pipeline
import time
import os
import logging
os.environ["TRANSFORMERS_CACHE"] = "C:\\Users\\Admin\\.cache\\Documents\\huggingface_cache"
# Load models with error handling
UPLOAD_FOLDER = 'upload'

# Set up logging to write to a file
logging.basicConfig(filename="audio_transcription.log",
                    level=logging.INFO,  # Adjust the log level as needed (e.g., DEBUG, INFO, WARNING)
                    format="%(asctime)s - %(levelname)s - %(message)s")
@st.cache_resource
def load_models():
    try:
        # Load Whisper model
        whisper_model = whisper.load_model("medium")  # Use "medium" or "large" for better accuracy
        if whisper_model is None:
            raise ValueError("Whisper model failed to load.")

        # Load PyAnnote diarization pipeline with token
        diarization_pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization@2.1",
                                    use_auth_token="YOUR_TOKEN")

        
        if diarization_pipeline is None:
            raise ValueError("Diarization model failed to load.")

        return whisper_model, diarization_pipeline

    except Exception as e:
        print(f"Error loading models: {e}")
        st.error(f"Error loading models: {e}")
        return None, None

# Initialize models
whisper_model, diarization_pipeline = load_models()

# Function to handle file upload and save to the 'upload' directory
def save_uploaded_file(uploaded_file):
    # Create a timestamp for the filename
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_extension = uploaded_file.name.split('.')[-1]
    file_name = f"{timestamp}_{uploaded_file.name}"
    
    # Save the uploaded file to the 'upload' directory with the timestamped filename
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path


# Function to process audio from a file path
def process_audio(audio_file_path):
    if whisper_model is None or diarization_pipeline is None:
        st.error("Models are not loaded properly. Please check the logs.")
        return None, None

    try:
        # Log the start of processing
        logging.info(f"Started processing audio file: {audio_file_path}")
        # Load audio with Whisper's load_audio function
        audio = whisper.load_audio(audio_file_path)
        audio = whisper.pad_or_trim(audio)  # Ensure the audio is the correct length

        # Transcribe with Whisper and get word-level timestamps
        transcription = whisper_model.transcribe(audio, word_timestamps=True)
        text = transcription["text"]
        word_timestamps = transcription["segments"]  # This contains the word timings
        detected_language = transcription["language"]
        
        # Log the detected language
        logging.info(f"Detected language: {detected_language}")

        # Perform speaker diarization
        diarization = diarization_pipeline({"uri": "audio", "audio": audio_file_path})

        # To store speaker-labeled text
        labeled_text = []
        
        # Process diarization and align it with transcribed words
        current_word_index = 0
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            start = segment.start
            end = segment.end
            labeled_segment = f"[{speaker}] "

            # Add words to the labeled segment based on the diarization timestamps
            while current_word_index < len(word_timestamps):
                word_info = word_timestamps[current_word_index]
                word_start = word_info["start"]
                word_end = word_info["end"]
                word_text = word_info["text"]

                # Check if the word's timing falls within the diarization segment
                if word_end <= end:
                    labeled_segment += word_text + " "
                    current_word_index += 1
                else:
                    break  # Exit when we've processed all words within the diarization segment
            
            labeled_text.append(labeled_segment.strip())
            # Log each speaker's contribution
            logging.info(f"Speaker {speaker} spoke: {labeled_segment.strip()}")
        # Log the completion of processing
        logging.info(f"Processing completed for: {audio_file_path}")

        return labeled_text, detected_language

    except Exception as e:
        st.error(f"Error processing audio: {e}")
        # Log the error
        logging.error(f"Error processing audio {audio_file_path}: {e}")
        print(f"Error processing audio: {e}")
        return None, None


# Streamlit App UI
st.title("Multilingual Audio Transcription with Speaker Labels")
st.write("Select an audio file from the 'upload' folder to transcribe and detect speakers.")

# Upload audio file
uploaded_file = st.file_uploader("Choose an audio file", type=["mp3", "wav", "m4a"])
if uploaded_file is not None:
    # Save the uploaded file
    audio_file_path = save_uploaded_file(uploaded_file)
    
    # Display file path for debugging purposes
    st.write(f"File uploaded successfully: {audio_file_path}")


    st.audio(audio_file_path, format="audio/wav")
    
    with st.spinner("Processing audio..."):
        try:
            labeled_text, detected_language = process_audio(audio_file_path)
            if labeled_text is not None:
                st.success("Processing complete!")

                # Display detected language
                st.subheader("Detected Language")
                st.write(f"**{detected_language}**")

                # Display speaker-labeled transcription
                st.subheader("Transcription with Speaker Labels")
                for line in labeled_text:
                    st.write(line)
        except Exception as e:
            st.error(f"An error occurred: {e}")

# Footer
st.markdown("---")
st.markdown(
    "Developed with  using [Whisper](https://github.com/openai/whisper) and "
    "[PyAnnote](https://github.com/pyannote/pyannote-audio)."
)
