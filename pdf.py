import sys
import os
import re
import csv
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from PyPDF2 import PdfReader


class PDFCategorizerGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PDF Scorer & Categorizer (Qt/PySide6)")
        self.setGeometry(100, 100, 700, 800)

        # Main widget and layout
        main_widget = QWidget()
        self.main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # --- Frame for Inputs ---
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.StyledPanel)
        input_layout = QVBoxLayout(input_frame)
        input_layout.addWidget(QLabel("<b>Configuration</b>"))

        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("OpenRouter API Key:"))
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_entry)
        input_layout.addLayout(api_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("OpenRouter Model:"))
        self.model_entry = QLineEdit("openai/gpt-3.5-turbo")
        model_layout.addWidget(self.model_entry)
        model_layout.addWidget(QLabel("(e.g., openai/gpt-3.5-turbo)"))
        input_layout.addLayout(model_layout)
        
        pdf_layout = QHBoxLayout()
        pdf_layout.addWidget(QLabel("PDFs Folder:"))
        self.pdf_folder_entry = QLineEdit()
        pdf_layout.addWidget(self.pdf_folder_entry)
        browse_pdf_btn = QPushButton("Browse")
        browse_pdf_btn.clicked.connect(self.browse_pdf_folder)
        pdf_layout.addWidget(browse_pdf_btn)
        input_layout.addLayout(pdf_layout)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output CSV File:"))
        self.output_file_entry = QLineEdit()
        output_layout.addWidget(self.output_file_entry)
        browse_output_btn = QPushButton("Browse")
        browse_output_btn.clicked.connect(self.browse_output_file)
        output_layout.addWidget(browse_output_btn)
        input_layout.addLayout(output_layout)
        self.main_layout.addWidget(input_frame)
        
        # --- Disclaimer Patterns ---
        disclaimer_frame = QFrame()
        disclaimer_frame.setFrameShape(QFrame.StyledPanel)
        disclaimer_layout = QVBoxLayout(disclaimer_frame)
        disclaimer_layout.addWidget(QLabel("<b>Disclaimer Removal Patterns (Regex)</b>"))
        self.disclaimer_text = QTextEdit()
        self.disclaimer_text.setPlainText("e.g., This document is for informational purposes only.*?\nDisclaimer:.*?All rights reserved\\.\n")
        disclaimer_layout.addWidget(self.disclaimer_text)
        self.main_layout.addWidget(disclaimer_frame)

        # --- AI Instructions ---
        instructions_frame = QFrame()
        instructions_frame.setFrameShape(QFrame.StyledPanel)
        instructions_layout = QVBoxLayout(instructions_frame)
        instructions_layout.addWidget(QLabel("<b>AI Categorization Instructions</b>"))
        self.instructions_text = QTextEdit()
        self.instructions_text.setPlainText("Analyze the text and categorize its content. Output relevant sections under specific keywords. For example:\n\n#GOLD\n[Text about gold price, production, or news]\n\n#AUD\n[Text related to Australian Dollar, economy, or RBA]\n\n#OTHER\n[Any other significant content not covered by specific keywords]")
        instructions_layout.addWidget(self.instructions_text)
        self.main_layout.addWidget(instructions_frame)

        # --- Process Button ---
        self.process_button = QPushButton("PROCESS PDFs, SCORE & CREATE CSV")
        font = self.process_button.font()
        font.setPointSize(14)
        font.setBold(True)
        self.process_button.setFont(font)
        self.process_button.setMinimumHeight(40)
        self.process_button.clicked.connect(self.process_pdfs)
        self.main_layout.addWidget(self.process_button)

        # --- Status Area ---
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QVBoxLayout(status_frame)
        status_layout.addWidget(QLabel("<b>Processing Status</b>"))
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        status_layout.addWidget(self.status_text)
        self.main_layout.addWidget(status_frame)

    def browse_pdf_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PDF Folder")
        if folder:
            self.pdf_folder_entry.setText(folder)

    def browse_output_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Output CSV File", "", "CSV files (*.csv);;All files (*.*)")
        if file:
            self.output_file_entry.setText(file)

    def log_status(self, message):
        self.status_text.append(message)
        QApplication.processEvents()

    def extract_and_clean_text(self, pdf_path):
        text = ""
        try:
            with open(pdf_path, 'rb') as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text: text += page_text
            disclaimer_patterns_raw = self.disclaimer_text.toPlainText().strip().split('\n')
            disclaimer_patterns = [p.strip() for p in disclaimer_patterns_raw if p.strip()]
            for pattern_str in disclaimer_patterns:
                try: text = re.sub(pattern_str, '', text, flags=re.IGNORECASE | re.DOTALL)
                except re.error as e: self.log_status(f"Warning: Invalid regex pattern '{pattern_str}': {e}")
            text = ' '.join(text.split())
        except Exception as e:
            self.log_status(f"Error reading {pdf_path}: {e}")
            return None
        return text

    def call_openrouter_api(self, text, instructions, model_name):
        api_key = self.api_key_entry.text()
        if not api_key:
            self.log_status("Error: OpenRouter API Key not provided.")
            return None
        if not model_name:
            self.log_status("Error: OpenRouter Model not specified.")
            return None
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}","Content-Type": "application/json","HTTP-Referer": "https://oanhhuynh-pdf-categorizer.com","X-Title": "Oanh's PDF Categorizer"}
        messages = [{"role": "system", "content": instructions},{"role": "user", "content": text}]
        payload = {"model": model_name, "messages": messages, "max_tokens": 1500, "temperature": 0.3}
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            response_json = response.json()
            if response_json and "choices" in response_json and response_json["choices"]:
                return response_json["choices"][0]["message"]["content"].strip()
            else: return "No categorization could be done by OpenRouter."
        except Exception as e:
            self.log_status(f"OpenRouter API Error: {e}")
            return None

    def process_pdfs(self):
        pdf_folder = self.pdf_folder_entry.text()
        output_file = self.output_file_entry.text()
        instructions = self.instructions_text.toPlainText().strip()
        model_to_use = self.model_entry.text().strip()

        if not self.api_key_entry.text(): QMessageBox.critical(self, "Error", "Please enter your OpenRouter API Key."); return
        if not model_to_use: QMessageBox.critical(self, "Error", "Please specify an OpenRouter Model."); return
        if not pdf_folder: QMessageBox.critical(self, "Error", "Please select the folder containing your PDF files."); return
        if not output_file: QMessageBox.critical(self, "Error", "Please select an output file."); return
        if not instructions: QMessageBox.warning(self, "Warning", "Please provide categorization instructions for the AI.");

        self.process_button.setEnabled(False)
        self.log_status("Starting PDF processing...")
        all_csv_rows = []
        
        try:
            pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
        except Exception as e:
            self.log_status(f"Error accessing PDF folder: {e}"); QMessageBox.critical(self, "Error", f"Error accessing PDF folder: {e}"); self.process_button.setEnabled(True); return

        if not pdf_files:
            self.log_status("No PDF files found in the selected folder.")
            QMessageBox.information(self, "Info", "No PDF files found in the selected folder.")
            self.process_button.setEnabled(True)
            return

        total_pdfs = len(pdf_files)
        for i, pdf_filename in enumerate(pdf_files):
            pdf_path = os.path.join(pdf_folder, pdf_filename)
            self.log_status(f"Processing {pdf_filename} ({i+1}/{total_pdfs})...")
            cleaned_text = self.extract_and_clean_text(pdf_path)
            
            if cleaned_text:
                self.log_status(f"Extracted text. Sending to OpenRouter...")
                categorized_text = self.call_openrouter_api(cleaned_text, instructions, model_to_use)
                
                if categorized_text:
                    self.log_status(f"Parsing and Scoring AI response for {pdf_filename}...")
                    chunks = re.split(r'(?m)^\s*(#\w+)\s*$', categorized_text)
                    content_blocks = chunks[1:] if chunks[0].strip() == '' else chunks
                    
                    for i in range(0, len(content_blocks), 2):
                        category = content_blocks[i].replace('#', '').strip()
                        content = content_blocks[i+1].strip() if (i + 1) < len(content_blocks) else ""
                        if content:
                            # --- NEW: SCORING LOGIC ---
                            # Count how many times the category keyword appears in the content
                            score = content.lower().count(category.lower())
                            
                            all_csv_rows.append({
                                'FileName': pdf_filename,
                                'Category': category,
                                'KeywordCountScore': score, # <-- New score column
                                'Content': content
                            })
                    self.log_status(f"Successfully processed {pdf_filename}.")
                else:
                    self.log_status(f"Failed to categorize {pdf_filename}.")
            else:
                self.log_status(f"Could not extract text from {pdf_filename}. Skipping.")
        
        if all_csv_rows:
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    # --- NEW: Added 'KeywordCountScore' to the header ---
                    fieldnames = ['FileName', 'Category', 'KeywordCountScore', 'Content']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_csv_rows)
                self.log_status(f"\nProcess finished. Results saved to: {output_file}")
                QMessageBox.information(self, "Success", f"Categorization complete. Results saved to: {output_file}")
            except Exception as e:
                self.log_status(f"Error saving CSV file: {e}"); QMessageBox.critical(self, "Error", f"Error saving CSV file: {e}")
        else:
            self.log_status("\nNo content was categorized.")
            QMessageBox.information(self, "Info", "No content was categorized. Please check inputs and status log.")
            
        self.process_button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFCategorizerGUI()
    window.show()
    sys.exit(app.exec())