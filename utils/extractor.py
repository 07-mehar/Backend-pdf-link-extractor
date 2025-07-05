from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
import uuid
import fitz  # PyMuPDF
import requests
from PyPDF2 import PdfMerger
import re

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
MERGED_FOLDER = 'merged_pdfs'
DOWNLOADS_FOLDER = 'downloads'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MERGED_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

# ✅ Updated to extract all links and also detect plain-text URLs
def extract_links_from_pdf(filepath):
    links = set()
    doc = fitz.open(filepath)
    url_regex = re.compile(r'https?://[^\s<>\)\]]+')  # More robust URL pattern

    for page_num, page in enumerate(doc, start=1):
        # Extract clickable link annotations
        for link in page.get_links():
            uri = link.get("uri")
            if uri:
                print(f"[Page {page_num}] Found link annotation: {uri}")
                links.add(uri)

        # Extract plain text URLs
        text = page.get_text()
        found_urls = url_regex.findall(text)
        for url in found_urls:
            print(f"[Page {page_num}] Found URL in text: {url}")
            links.add(url)

    print(f"[INFO] Total unique links extracted: {len(links)}")
    return list(links)

def download_pdfs(links):
    file_paths = []
    for url in links:
        try:
            print(f"[INFO] Downloading: {url}")
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("application/pdf"):
                filename = f"{uuid.uuid4()}.pdf"
                filepath = os.path.join(DOWNLOADS_FOLDER, filename)
                with open(filepath, "wb") as f:
                    f.write(r.content)
                file_paths.append(filepath)
                print(f"[SUCCESS] Downloaded: {url}")
            else:
                print(f"[SKIPPED] Not a valid PDF or failed response: {url}")
        except Exception as e:
            print(f"[ERROR] Download failed for {url} - {e}")
    return file_paths

def merge_pdfs(pdf_paths, output_path):
    merger = PdfMerger()
    for path in pdf_paths:
        merger.append(path)
    merger.write(output_path)
    merger.close()
    print(f"[INFO] Merged {len(pdf_paths)} PDFs into {output_path}")

@app.route('/upload', methods=['POST'])
def upload_pdf():
    file = request.files['file']
    filename = f"{uuid.uuid4()}.pdf"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    print(f"[INFO] Uploaded file saved to: {filepath}")

    links = extract_links_from_pdf(filepath)
    print(f"[INFO] Extracted links: {links}")

    if not links:
        return jsonify({"status": "no_links", "message": "No links found"}), 200

    downloaded = download_pdfs(links)
    if not downloaded:
        return jsonify({"status": "download_failed", "message": "No valid PDFs"}), 400

    merged_filename = f"merged_{uuid.uuid4()}.pdf"
    merged_filepath = os.path.join(MERGED_FOLDER, merged_filename)
    merge_pdfs(downloaded, merged_filepath)

    return jsonify({
        "status": "success",
        "mergedPdfUrl": f"/download/{merged_filename}",
        "extractedLinks": links
    })

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(MERGED_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(port=8000, debug=True)
