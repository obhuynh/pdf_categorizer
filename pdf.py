import sys
import os
import re
import csv
import json
import time
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QFrame, QProgressBar, QCheckBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PyPDF2 import PdfReader

try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMER_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMER_AVAILABLE = False


# --- Constants for DeepSeek API ---
CONFIG_FILE = "config.json"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
SEMANTIC_SCORE_MODEL = 'all-MiniLM-L6-v2'
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"

# --- Worker for background processing ---
class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    status_update = Signal(str)
    progress_update = Signal(int)

class PdfProcessorWorker(QObject):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_cancelled = False
        self.signals = WorkerSignals()
        if SENTENCE_TRANSFORMER_AVAILABLE:
            try:
                self.score_model = SentenceTransformer(SEMANTIC_SCORE_MODEL)
            except Exception as e:
                self.signals.error.emit(f"Could not load scoring model: {e}")
                self.score_model = None
        else:
            self.score_model = None

    def run(self):
        self.log_status("Starting PDF processing worker thread...")
        processed_files = {}

        try:
            pdf_files = [f for f in os.listdir(self.config['pdf_folder']) if f.lower().endswith(".pdf")]
            total_pdfs = len(pdf_files)
            if not pdf_files:
                self.log_status("No PDF files found.")
                self.signals.finished.emit()
                return

            for i, pdf_filename in enumerate(pdf_files):
                if self.is_cancelled:
                    self.log_status("Processing cancelled.")
                    break
                self.signals.progress_update.emit(int(((i + 1) / total_pdfs) * 100))
                self.log_status(f"--- Processing {pdf_filename} ({i+1}/{total_pdfs}) ---")
                
                processed_files[pdf_filename] = {'FileName': pdf_filename}
                pdf_path = os.path.join(self.config['pdf_folder'], pdf_filename)
                categorized_data = self.process_single_pdf(pdf_path)
                if categorized_data:
                    processed_files[pdf_filename].update(categorized_data)

            if not self.is_cancelled:
                self.write_pivoted_csv(processed_files)

        except Exception as e:
            self.signals.error.emit(f"An unexpected error occurred: {e}")
        finally:
            self.signals.finished.emit()

    def process_single_pdf(self, pdf_path):
        self.log_status(f"Extracting text...")
        cleaned_text = self.extract_and_clean_text(pdf_path)
        if not cleaned_text: return None

        self.log_status("Sending text to DeepSeek for categorization...")
        categorized_text = self.call_deepseek_api(cleaned_text)
        if not categorized_text: return None

        self.log_status(f"Parsing and Scoring AI response...")
        return self.parse_and_score_response(categorized_text)
        
    def extract_and_clean_text(self, pdf_path):
        text = ""
        try:
            with open(pdf_path, 'rb') as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text: text += page_text + "\n"
            disclaimer_patterns = [p.strip() for p in self.config['disclaimers'] if p.strip()]
            for pattern_str in disclaimer_patterns:
                try: text = re.sub(pattern_str, '', text, flags=re.IGNORECASE | re.DOTALL)
                except re.error as e: self.log_status(f"Warning: Invalid regex: '{pattern_str}': {e}")
            return ' '.join(text.split())
        except Exception as e:
            self.log_status(f"Error reading {pdf_path}: {e}")
            return None

    def call_deepseek_api(self, text):
        headers = { "Authorization": f"Bearer {self.config['api_key']}", "Content-Type": "application/json" }
        messages = [{"role": "system", "content": self.config['instructions']}, {"role": "user", "content": text}]
        payload = {"model": self.config['model'], "messages": messages, "max_tokens": 4096, "temperature": 0.2}

        for attempt in range(3):
            try:
                self.log_status(f"Contacting DeepSeek API (Attempt {attempt + 1})...")
                response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
                response.raise_for_status()
                response_json = response.json()
                if response_json.get("choices"):
                    raw_response_text = response_json["choices"][0]["message"]["content"].strip()
                    
                    self.log_status(f"---- AI RAW RESPONSE ----\n{raw_response_text}\n--------------------------")
                    
                    return raw_response_text
                else: 
                    self.log_status("---- AI RAW RESPONSE ----\nAI response was empty or had no 'choices'.\n--------------------------")
                    return "AI response was empty."
            except requests.exceptions.RequestException as e:
                self.log_status(f"DeepSeek API Error (Attempt {attempt + 1}/3): {e}")
                time.sleep(2 ** attempt)
        self.log_status("DeepSeek API failed after multiple retries.")
        return None

    def parse_and_score_response(self, categorized_text):
        file_data = {}
        chunks = re.split(r'(?m)^\s*(#\w+)\s*$', categorized_text)
        content_blocks = chunks[1:] if chunks and chunks[0].strip() == '' else chunks
        if not content_blocks:
            self.log_status(f"Warning: Could not parse any #KEYWORDS from AI response.")
            return file_data
            
        for i in range(0, len(content_blocks), 2):
            if i + 1 < len(content_blocks):
                category = content_blocks[i].replace('#', '').strip().upper()
                content = content_blocks[i+1].strip()
                if content:
                    score = -1
                    if self.score_model:
                        try:
                            cat_embed = self.score_model.encode(category, convert_to_tensor=True)
                            con_embed = self.score_model.encode(content, convert_to_tensor=True)
                            score = round(util.pytorch_cos_sim(cat_embed, con_embed).item(), 4)
                        except Exception as e:
                            self.log_status(f"Could not calculate score for '{category}': {e}")
                    
                    file_data[f'{category}_Score'] = score
                    file_data[f'{category}_Content'] = content
        
        self.log_status(f"Successfully parsed and scored {len(file_data) // 2} categories.")
        return file_data

    def write_pivoted_csv(self, processed_files_dict):
        if not processed_files_dict:
            self.log_status("\nProcess finished, but no content was categorized.")
            return

        all_headers = set(['FileName'])
        for file_data in processed_files_dict.values():
            all_headers.update(file_data.keys())
        
        sorted_headers = ['FileName'] + sorted([h for h in all_headers if h != 'FileName'])

        try:
            with open(self.config['output_file'], 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted_headers)
                writer.writeheader()
                writer.writerows(processed_files_dict.values())
            self.log_status(f"\nSUCCESS! Results saved in pivoted format to: {self.config['output_file']}")
        except Exception as e:
            self.signals.error.emit(f"Error saving CSV file: {e}")

    def stop(self):
        self.is_cancelled = True
        self.log_status("Cancellation signal received.")

    def log_status(self, message):
        self.signals.status_update.emit(message)


# --- Main Application Window ---
class PDFCategorizerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Scorer & Categorizer (DeepSeek Edition)")
        self.setGeometry(100, 100, 800, 900)
        self.thread = None; self.worker = None
        main_widget = QWidget()
        self.main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        self.setup_ui()
        self.load_settings()

    def build_prompt_from_keywords(self, keywords_str, include_other):
        if not keywords_str.strip(): return "" 

        keywords = [k.strip().upper() for k in keywords_str.split(',')]
        
        base_prompt = (
            "You are a highly specialized text extraction tool. Your one and only job is to find and extract text that is strictly relevant to the category headings provided below. "
            "DO NOT create any new category headings that are not in the list. "
            "DO NOT extract information for any topics not listed in the headings. "
            "For each heading, provide a summary. If no relevant text is found for a heading, you MUST write 'No content found for [HEADING_NAME].'"
        )

        allowed_headings_list = [f"#{k}" for k in keywords]
        if include_other:
            allowed_headings_list.append("#OTHER")
        
        allowed_headings_instruction = f"The ONLY category headings you are allowed to use in your response are: {', '.join(allowed_headings_list)}."

        keyword_examples = []
        for keyword in keywords:
            example = (f"#{keyword}\n"
                       f"[If you find any content related to {keyword}, summarize it here as a bulleted list. If you find nothing, write 'No content found for {keyword}.']")
            keyword_examples.append(example)

        if include_other:
            other_example = ("#OTHER\n"
                             "[If you find any other significant financial topics, summarize them here as a bulleted list. If not, write 'No other significant content found.']")
            keyword_examples.append(other_example)

        final_prompt = (f"{base_prompt}\n\n{allowed_headings_instruction}\n\n"
                        f"--- EXAMPLES OF REQUIRED FORMAT ---\n" + "\n\n".join(keyword_examples))
        
        self.log_status("Built final restrictive prompt for AI...")
        return final_prompt

    def setup_ui(self):
        input_frame = QFrame(); input_frame.setFrameShape(QFrame.StyledPanel)
        input_layout = QVBoxLayout(input_frame)
        config_header_layout = QHBoxLayout()
        config_header_layout.addWidget(QLabel("<b>Configuration</b>")); config_header_layout.addStretch()
        save_btn = QPushButton("Save Settings"); save_btn.clicked.connect(self.save_settings)
        config_header_layout.addWidget(save_btn)
        load_btn = QPushButton("Load Settings"); load_btn.clicked.connect(self.load_settings)
        config_header_layout.addWidget(load_btn)
        input_layout.addLayout(config_header_layout)
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("DeepSeek API Key:"))
        self.api_key_entry = QLineEdit(); self.api_key_entry.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_entry)
        input_layout.addLayout(api_layout)
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("DeepSeek Model:"))
        self.model_entry = QLineEdit(DEFAULT_DEEPSEEK_MODEL)
        model_layout.addWidget(self.model_entry)
        input_layout.addLayout(model_layout)
        pdf_layout = QHBoxLayout()
        pdf_layout.addWidget(QLabel("PDFs Folder:"))
        self.pdf_folder_entry = QLineEdit()
        pdf_layout.addWidget(self.pdf_folder_entry)
        browse_pdf_btn = QPushButton("Browse"); browse_pdf_btn.clicked.connect(self.browse_pdf_folder)
        pdf_layout.addWidget(browse_pdf_btn)
        input_layout.addLayout(pdf_layout)
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output CSV File:"))
        self.output_file_entry = QLineEdit()
        output_layout.addWidget(self.output_file_entry)
        browse_output_btn = QPushButton("Browse"); browse_output_btn.clicked.connect(self.browse_output_file)
        output_layout.addWidget(browse_output_btn)
        input_layout.addLayout(output_layout)
        self.main_layout.addWidget(input_frame)
        
        disclaimer_frame = QFrame(); disclaimer_frame.setFrameShape(QFrame.StyledPanel)
        disclaimer_layout = QVBoxLayout(disclaimer_frame)
        disclaimer_layout.addWidget(QLabel("<b>Disclaimer Removal Patterns (Regex - One per line)</b>"))
        self.disclaimer_text = QTextEdit("This document is for informational purposes only.*?\nDisclaimer:.*?All rights reserved\\.")
        disclaimer_layout.addWidget(self.disclaimer_text)
        self.main_layout.addWidget(disclaimer_frame)
        
        instructions_frame = QFrame(); instructions_frame.setFrameShape(QFrame.StyledPanel)
        instructions_layout = QVBoxLayout(instructions_frame)
        instructions_layout.addWidget(QLabel("<b>Keywords to Extract</b>"))
        self.keywords_entry = QLineEdit(); self.keywords_entry.setPlaceholderText("e.g., GOLD, AUD, Oil, Bonds")
        instructions_layout.addWidget(self.keywords_entry)
        instructions_layout.addWidget(QLabel("Enter keywords separated by commas."))
        
        self.include_other_checkbox = QCheckBox("Include an '#OTHER' category for miscellaneous content")
        self.include_other_checkbox.setChecked(True)
        instructions_layout.addWidget(self.include_other_checkbox)
        
        self.main_layout.addWidget(instructions_frame)
        
        action_layout = QHBoxLayout()
        self.process_button = QPushButton("PROCESS PDFs"); self.process_button.clicked.connect(self.start_processing)
        font = self.process_button.font(); font.setPointSize(14); font.setBold(True)
        self.process_button.setFont(font); self.process_button.setMinimumHeight(40)
        action_layout.addWidget(self.process_button)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.cancel_processing)
        font = self.cancel_button.font(); font.setPointSize(14)
        self.cancel_button.setFont(font); self.cancel_button.setMinimumHeight(40); self.cancel_button.setEnabled(False)
        action_layout.addWidget(self.cancel_button)
        self.main_layout.addLayout(action_layout)
        
        self.progress_bar = QProgressBar(); self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)
        
        status_frame = QFrame(); status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QVBoxLayout(status_frame)
        status_layout.addWidget(QLabel("<b>Processing Status Log</b>"))
        self.status_text = QTextEdit(); self.status_text.setReadOnly(True)
        status_layout.addWidget(self.status_text)
        self.main_layout.addWidget(status_frame)
    
    def browse_pdf_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PDF Folder")
        if folder: self.pdf_folder_entry.setText(folder)

    def browse_output_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Output CSV File", "", "CSV files (*.csv)")
        if file: self.output_file_entry.setText(file)

    def log_status(self, message):
        self.status_text.append(message)
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum())

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def validate_inputs(self):
        if not self.api_key_entry.text():
            QMessageBox.critical(self, "Error", "Please enter your DeepSeek API Key.")
            return False
        if not self.keywords_entry.text().strip():
            QMessageBox.critical(self, "Error", "Please enter at least one keyword to extract.")
            return False
        if not os.path.isdir(self.pdf_folder_entry.text()):
            QMessageBox.critical(self, "Error", "The selected PDF folder is not valid.")
            return False
        if not self.output_file_entry.text():
            QMessageBox.critical(self, "Error", "Please select an output CSV file path.")
            return False
        return True

    def start_processing(self):
        if not self.validate_inputs(): return
        self.process_button.setEnabled(False); self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0); self.status_text.clear()

        keywords = self.keywords_entry.text()
        should_include_other = self.include_other_checkbox.isChecked()
        instructions = self.build_prompt_from_keywords(keywords, should_include_other)
        
        if not instructions:
            QMessageBox.critical(self, "Error", "Could not start: Instructions could not be built from keywords.")
            self.process_button.setEnabled(True); self.cancel_button.setEnabled(False)
            return

        config = {
            'api_key': self.api_key_entry.text(), 'model': self.model_entry.text().strip(),
            'pdf_folder': self.pdf_folder_entry.text(), 'output_file': self.output_file_entry.text(),
            'instructions': instructions, 'disclaimers': self.disclaimer_text.toPlainText().strip().split('\n')
        }
        
        self.thread = QThread()
        self.worker = PdfProcessorWorker(config)
        self.worker.moveToThread(self.thread)
        self.worker.signals.status_update.connect(self.log_status)
        self.worker.signals.progress_update.connect(self.update_progress)
        self.worker.signals.error.connect(self.processing_error)
        self.worker.signals.finished.connect(self.processing_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def cancel_processing(self):
        if self.worker: self.worker.stop()
        self.cancel_button.setEnabled(False)
        
    def processing_finished(self):
        if self.worker and not self.worker.is_cancelled:
            QMessageBox.information(self, "Success", "Processing complete. See log for details.")
        if self.thread: self.thread.quit(); self.thread.wait()
        self.thread = self.worker = None
        self.process_button.setEnabled(True); self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(100)

    def processing_error(self, error_message):
        self.log_status(f"ERROR: {error_message}")
        QMessageBox.critical(self, "Processing Error", error_message)

    def save_settings(self):
        settings = {
            'api_key': self.api_key_entry.text(), 'model': self.model_entry.text(),
            'pdf_folder': self.pdf_folder_entry.text(), 'output_file': self.output_file_entry.text(),
            'disclaimers': self.disclaimer_text.toPlainText(), 'keywords': self.keywords_entry.text(),
            'include_other': self.include_other_checkbox.isChecked()
        }
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(settings, f, indent=4)
            self.log_status("Settings saved successfully.")
        except Exception as e: self.log_status(f"Error saving settings: {e}")

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    settings = json.load(f)
                    self.api_key_entry.setText(settings.get('api_key', ''))
                    self.model_entry.setText(settings.get('model', DEFAULT_DEEPSEEK_MODEL))
                    self.pdf_folder_entry.setText(settings.get('pdf_folder', ''))
                    self.output_file_entry.setText(settings.get('output_file', ''))
                    self.disclaimer_text.setPlainText(settings.get('disclaimers', ''))
                    self.keywords_entry.setText(settings.get('keywords', ''))
                    self.include_other_checkbox.setChecked(settings.get('include_other', True))
                self.log_status("Settings loaded successfully.")
            else: self.log_status("No config file found. Using default settings.")
        except Exception as e: self.log_status(f"Error loading settings: {e}")

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning(): self.cancel_processing()
        self.save_settings()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFCategorizerGUI()
    window.show()
    sys.exit(app.exec())