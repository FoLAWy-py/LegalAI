// Independent page truth for externally generated fixtures (macOS PDFKit, not pypdf).
// Usage: osascript -l JavaScript pdfkit_page_numbers.js <file.pdf>
// Prints JSON: for each page (1-based), the 3-digit line numbers ("第NNN") shown on it, and whether
// the title line (containing "SYNTHETIC ZZ") is on it.
ObjC.import("PDFKit");

function run(argv) {
  var doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
  var pages = [];
  for (var i = 0; i < doc.pageCount; i++) {
    var text = ObjC.unwrap(doc.pageAtIndex(i).string) || "";
    var numbers = (text.match(/第(\d{3})/g) || []).map(function (m) { return parseInt(m.slice(1), 10); });
    pages.push({ page: i + 1, line_numbers: numbers, has_title: text.indexOf("SYNTHETIC ZZ") >= 0 });
  }
  return JSON.stringify({ generator: "macOS PDFKit", pages: pages });
}
