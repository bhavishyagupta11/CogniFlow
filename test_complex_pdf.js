const fs = require('fs');
const pdf = require('pdf-parse');

async function testComplexPdf() {
  const fileUrl = 'https://arxiv.org/pdf/1706.03762'; // arXiv without .pdf usually redirects to the PDF
  const filePath = 'attention.pdf';

  console.log("Downloading Attention Is All You Need PDF via fetch...");
  
  const res = await fetch('https://raw.githubusercontent.com/mozilla/pdf.js/master/test/pdfs/tracemonkey.pdf');
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  const arrayBuffer = await res.arrayBuffer();
  fs.writeFileSync(filePath, Buffer.from(arrayBuffer));

  console.log("Download complete. Parsing...");
  const buffer = fs.readFileSync(filePath);
  try {
    const data = await pdf(buffer);
    console.log("Extraction successful!");
    console.log("Extracted length:", data.text.length);
    console.log("Snippet (first 500 chars):");
    console.log("-----------------------");
    console.log(data.text.substring(0, 500));
    console.log("-----------------------");
  } catch (err) {
    console.error("Extraction failed:", err);
  }
}

testComplexPdf();
