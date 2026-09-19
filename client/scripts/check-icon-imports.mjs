// Static AST/pattern check for all JSX files to prevent undeclared Lucide icon references
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, "../src");

function walk(dir) {
  let files = [];
  for (const item of fs.readdirSync(dir)) {
    const p = path.join(dir, item);
    const stat = fs.statSync(p);
    if (stat.isDirectory()) {
      if (item !== "node_modules" && item !== "dist" && item !== ".git") {
        files = files.concat(walk(p));
      }
    } else if (p.endsWith(".jsx") || p.endsWith(".js") || p.endsWith(".tsx") || p.endsWith(".ts")) {
      files.push(p);
    }
  }
  return files;
}

const allFiles = walk(srcDir);
const issues = [];

// Common Lucide React icon names to guard
const knownLucideIcons = new Set([
  "CheckCircle2", "CheckCircle", "AlertCircle", "AlertTriangle", "XCircle", "FileText", "ShieldCheck",
  "Database", "Cpu", "Server", "ChevronDown", "ChevronRight", "ChevronUp", "ChevronLeft", "Layers",
  "Search", "Clock", "Info", "RefreshCw", "Download", "Upload", "UploadCloud", "Trash2", "Eye",
  "ExternalLink", "Copy", "Check", "Send", "Paperclip", "HelpCircle", "Activity", "BookOpen",
  "MessageSquare", "Sparkles", "Terminal", "Filter", "Sliders", "Settings", "LogOut", "User",
  "Lock", "ArrowRight", "ArrowLeft", "Loader2", "Maximize2", "RotateCcw", "ZoomIn", "ZoomOut"
]);

for (const file of allFiles) {
  const code = fs.readFileSync(file, "utf8");
  // Find all JSX elements like <SomeIcon ...
  const jsxMatches = [...code.matchAll(/<([A-Z][a-zA-Z0-9]+)/g)].map((m) => m[1]);

  // Find imports from lucide-react
  const lucideMatches = [...code.matchAll(/import\s*\{([^}]+)\}\s*from\s*["']lucide-react["']/g)];
  const importedLucideIcons = new Set();
  for (const match of lucideMatches) {
    const symbols = match[1].split(",").map((s) => s.trim().split(/\s+as\s+/).pop().trim()).filter(Boolean);
    symbols.forEach((s) => importedLucideIcons.add(s));
  }

  for (const icon of jsxMatches) {
    if (knownLucideIcons.has(icon)) {
      const isImported = importedLucideIcons.has(icon) || new RegExp(`\\b${icon}\\b.*from`).test(code);
      const isDeclared = new RegExp(`(?:const|let|var|function|class)\\s+${icon}\\b`).test(code);
      if (!isImported && !isDeclared) {
        issues.push({ file: path.relative(srcDir, file), icon });
      }
    }
  }
}

if (issues.length > 0) {
  console.error("❌ FAILED: Undefined Lucide icon references detected in client codebase:");
  issues.forEach((iss) => console.error(`   - ${iss.file}: <${iss.icon} /> is used but not imported!`));
  process.exit(1);
} else {
  console.log("✅ PASSED: All Lucide icon references in client/src are correctly imported.");
  process.exit(0);
}
