import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Lock, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";

export function PdfPasswordDialog({
  isOpen,
  file,
  errorMessage,
  isProcessing,
  onSubmit,
  onCancel,
}) {
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!password.trim() || isProcessing) return;
    onSubmit(password);
    // Clear password from local state immediately after submit
    setPassword("");
  };

  const handleClose = () => {
    setPassword("");
    onCancel();
  };

  if (!isOpen) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
      <DialogContent className="sm:max-w-md bg-[var(--panel-bg)] border-[var(--panel-border)] text-[var(--text-primary)]">
        <DialogHeader>
          <div className="flex items-center gap-2 text-amber-500 mb-1">
            <Lock className="h-5 w-5" />
            <DialogTitle className="font-mono text-sm uppercase tracking-wider">
              Encrypted PDF Document
            </DialogTitle>
          </div>
          <DialogDescription className="font-mono text-xs text-[var(--text-secondary)]">
            <strong className="text-[var(--text-primary)]">{file?.name}</strong> is password-protected.
            Please enter the document password to unlock and process it.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {errorMessage && (
            <div className="flex items-start gap-2 p-2.5 rounded-[3px] border border-rose-500/30 bg-rose-500/10 text-rose-400 font-mono text-xs">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <Label
              htmlFor="pdf-password-input"
              className="font-mono text-xs text-[var(--text-secondary)] font-bold uppercase tracking-wider"
            >
              PDF Password
            </Label>
            <div className="relative">
              <Input
                id="pdf-password-input"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter document password..."
                autoFocus
                disabled={isProcessing}
                className="font-mono text-xs bg-[var(--panel-inner)] border-[var(--panel-border)] pr-10 focus:border-amber-500 text-[var(--text-primary)]"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                disabled={isProcessing}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="font-mono text-[10px] text-[var(--text-muted)]">
              The password is used solely in-memory to decrypt this file and is never stored.
            </p>
          </div>

          <DialogFooter className="flex justify-end gap-2 pt-2 border-t border-[var(--panel-border)]">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleClose}
              disabled={isProcessing}
              className="font-mono text-xs border-[var(--panel-border)] bg-[var(--panel-inner)] hover:bg-[var(--panel-border)] cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!password.trim() || isProcessing}
              className="font-mono text-xs bg-amber-500 hover:bg-amber-600 text-black font-bold uppercase cursor-pointer"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  Decrypting...
                </>
              ) : (
                "Unlock & Process"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
