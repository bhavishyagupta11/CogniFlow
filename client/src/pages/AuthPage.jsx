import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ShieldCheck,
  User,
  Eye,
  EyeOff,
  CheckCircle2,
  LogIn,
  UserPlus,
  LogOut,
  ArrowRight,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { useAuthStore } from "@/store/use-auth-store";
import { useChatStore } from "@/store/use-chat-store";

export function AuthPage() {
  const navigate = useNavigate();
  const {
    user,
    isAuthenticated,
    login,
    register,
    logout,
    sessionId,
  } = useAuthStore();

  const [activeTab, setActiveTab] = useState("login"); // 'login' | 'register'
  const [submitting, setSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Register form state
  const [regName, setRegName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPassword, setRegConfirmPassword] = useState("");
  const [showRegPassword, setShowRegPassword] = useState(false);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    if (!loginEmail.trim() || !loginPassword) {
      setAuthError("Please enter both email and password.");
      return;
    }

    setSubmitting(true);
    try {
      await login(loginEmail.trim(), loginPassword);
      toast.success("Authenticated successfully. Restoring conversations…");
      await useChatStore.getState().fetchUserConversations(false);
      navigate("/");
    } catch (err) {
      setAuthError(err.message || "Failed to sign in. Please verify your credentials.");
      toast.error(err.message || "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");

    if (!regName.trim()) {
      setAuthError("Full Name is required.");
      return;
    }
    if (!regEmail.trim()) {
      setAuthError("Email address is required.");
      return;
    }
    if (!regPassword) {
      setAuthError("Password is required.");
      return;
    }
    if (regPassword.length < 6) {
      setAuthError("Password must be at least 6 characters long.");
      return;
    }
    if (regPassword !== regConfirmPassword) {
      setAuthError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await register(regName.trim(), regEmail.trim(), regPassword, regConfirmPassword);
      toast.success("Account created successfully!");
      await useChatStore.getState().fetchUserConversations(false);
      navigate("/");
    } catch (err) {
      setAuthError(err.message || "Registration failed. Please try again.");
      toast.error(err.message || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    useChatStore.getState().clearUserChatState();
    toast.info("Logged out. Switched to fresh guest session.");
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full space-y-6">
      {/* Header */}
      <div>
        <h2 className="font-mono text-base font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-[#f97316]" />
          CogniFlow Identity & Persistence
        </h2>
        <p className="font-mono text-xs text-[var(--text-muted)] mt-1">
          Authentication is optional. Log in or create an account anytime to durably persist chats, missions, and uploaded documents.
        </p>
      </div>

      {/* Main Authentication Card */}
      {isAuthenticated && user ? (
        /* Authenticated View */
        <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
          <CardHeader className="border-b border-[var(--panel-border)] pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  Active Operator Account
                </CardTitle>
                <CardDescription className="font-mono text-[11px] text-[var(--text-muted)] mt-0.5">
                  Authenticated session active. Conversations and documents are durably persisted to your account.
                </CardDescription>
              </div>
              <div className="flex items-center gap-1.5 text-xs font-mono font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-[2px] border border-emerald-500/20">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>AUTHENTICATED</span>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-4 pt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] space-y-1">
                <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] font-bold">
                  OPERATOR NAME
                </div>
                <div className="text-xs font-mono font-bold text-[var(--text-primary)] truncate">
                  {user.name}
                </div>
              </div>

              <div className="p-3 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] space-y-1">
                <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] font-bold">
                  EMAIL ADDRESS
                </div>
                <div className="text-xs font-mono font-bold text-[var(--text-primary)] truncate">
                  {user.email}
                </div>
              </div>

              <div className="p-3 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] space-y-1 md:col-span-2">
                <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] font-bold">
                  USER IDENTIFIER (ISOLATION KEY)
                </div>
                <div className="text-xs font-mono text-[var(--text-secondary)] font-mono truncate">
                  {user.id}
                </div>
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex items-center justify-between border-t border-[var(--panel-border)] pt-4">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="rounded-[2px] font-mono text-xs border-[var(--panel-border)] text-[var(--text-muted)] hover:text-rose-500 hover:border-rose-500 cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5 mr-1.5" />
              SIGN OUT
            </Button>

            <Button
              type="button"
              size="sm"
              onClick={() => navigate("/")}
              className="rounded-[2px] font-mono text-xs bg-[#f97316] text-white font-bold uppercase hover:bg-[#ea580c] cursor-pointer"
            >
              <span>CONTINUE CHATTING</span>
              <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
            </Button>
          </CardFooter>
        </Card>
      ) : (
        /* Unauthenticated View: Guest Status + Sign In / Sign Up */
        <div className="space-y-4">
          {/* Guest Status Banner */}
          <div className="p-4 rounded-[4px] border border-amber-500/30 bg-amber-500/5 flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <div className="font-mono text-xs font-bold text-amber-500 uppercase tracking-wider">
                Guest Mode Active
              </div>
              <p className="font-mono text-xs text-[var(--text-secondary)] mt-0.5">
                You can use CogniFlow without an account. Your chats and uploaded documents are kept temporarily in this session.
                Sign in or create an account at any time to automatically save your current work.
              </p>
              {sessionId && (
                <div className="font-mono text-[10px] text-[var(--text-muted)] mt-1.5 truncate">
                  SESSION ID: <span className="text-[var(--text-secondary)]">{sessionId}</span>
                </div>
              )}
            </div>
          </div>

          <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
            {/* Tab Selection */}
            <div className="flex border-b border-[var(--panel-border)]">
              <button
                type="button"
                onClick={() => {
                  setActiveTab("login");
                  setAuthError("");
                }}
                className={`flex-1 py-2.5 px-4 font-mono text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer flex items-center justify-center gap-1.5 ${
                  activeTab === "login"
                    ? "border-b-2 border-[#f97316] text-[#f97316] bg-[var(--panel-inner)]/50"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
                }`}
              >
                <LogIn className="h-3.5 w-3.5" />
                <span>SIGN IN</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("register");
                  setAuthError("");
                }}
                className={`flex-1 py-2.5 px-4 font-mono text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer flex items-center justify-center gap-1.5 ${
                  activeTab === "register"
                    ? "border-b-2 border-[#f97316] text-[#f97316] bg-[var(--panel-inner)]/50"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
                }`}
              >
                <UserPlus className="h-3.5 w-3.5" />
                <span>CREATE ACCOUNT</span>
              </button>
            </div>

            {authError && (
              <div className="p-3 m-4 mb-0 rounded-[3px] bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-mono flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{authError}</span>
              </div>
            )}

            {activeTab === "login" ? (
              /* Sign In Form */
              <form onSubmit={handleLoginSubmit}>
                <CardContent className="space-y-4 pt-4">
                  <div className="space-y-1.5">
                    <Label
                      htmlFor="loginEmail"
                      className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                    >
                      Email Address
                    </Label>
                    <Input
                      id="loginEmail"
                      type="email"
                      required
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                      placeholder="user@example.com"
                      className="rounded-[3px] border-[var(--panel-border)] bg-[var(--panel-inner)] font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[#f97316]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label
                      htmlFor="loginPassword"
                      className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                    >
                      Password
                    </Label>
                    <div className="relative">
                      <Input
                        id="loginPassword"
                        type={showLoginPassword ? "text" : "password"}
                        required
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        placeholder="••••••••"
                        className="rounded-[3px] border-[var(--panel-border)] bg-[var(--panel-inner)] font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] pr-10 focus:border-[#f97316]"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLoginPassword(!showLoginPassword)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                        tabIndex={-1}
                      >
                        {showLoginPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </CardContent>

                <CardFooter className="border-t border-[var(--panel-border)] pt-4 flex justify-between items-center">
                  <div className="text-[10px] font-mono text-[var(--text-muted)]">
                    Don't have an account?{" "}
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTab("register");
                        setAuthError("");
                      }}
                      className="text-[#f97316] hover:underline cursor-pointer font-bold uppercase"
                    >
                      Sign Up
                    </button>
                  </div>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={submitting}
                    className="rounded-[2px] font-mono text-xs bg-[#f97316] text-white font-bold uppercase hover:bg-[#ea580c] cursor-pointer"
                  >
                    {submitting ? "AUTHENTICATING…" : "SIGN IN"}
                  </Button>
                </CardFooter>
              </form>
            ) : (
              /* Sign Up Form */
              <form onSubmit={handleRegisterSubmit}>
                <CardContent className="space-y-4 pt-4">
                  <div className="space-y-1.5">
                    <Label
                      htmlFor="regName"
                      className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                    >
                      Full Name
                    </Label>
                    <Input
                      id="regName"
                      type="text"
                      required
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder="Operator Name"
                      className="rounded-[3px] border-[var(--panel-border)] bg-[var(--panel-inner)] font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[#f97316]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label
                      htmlFor="regEmail"
                      className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                    >
                      Email Address
                    </Label>
                    <Input
                      id="regEmail"
                      type="email"
                      required
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      placeholder="operator@example.com"
                      className="rounded-[3px] border-[var(--panel-border)] bg-[var(--panel-inner)] font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[#f97316]"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label
                        htmlFor="regPassword"
                        className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                      >
                        Password
                      </Label>
                      <div className="relative">
                        <Input
                          id="regPassword"
                          type={showRegPassword ? "text" : "password"}
                          required
                          value={regPassword}
                          onChange={(e) => setRegPassword(e.target.value)}
                          placeholder="••••••••"
                          className="rounded-[3px] border-[var(--panel-border)] bg-[var(--panel-inner)] font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] pr-10 focus:border-[#f97316]"
                        />
                        <button
                          type="button"
                          onClick={() => setShowRegPassword(!showRegPassword)}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                          tabIndex={-1}
                        >
                          {showRegPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <Label
                        htmlFor="regConfirmPassword"
                        className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                      >
                        Confirm Password
                      </Label>
                      <Input
                        id="regConfirmPassword"
                        type={showRegPassword ? "text" : "password"}
                        required
                        value={regConfirmPassword}
                        onChange={(e) => setRegConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        className="rounded-[3px] border-[var(--panel-border)] bg-[var(--panel-inner)] font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[#f97316]"
                      />
                    </div>
                  </div>
                </CardContent>

                <CardFooter className="border-t border-[var(--panel-border)] pt-4 flex justify-between items-center">
                  <div className="text-[10px] font-mono text-[var(--text-muted)]">
                    Already have an account?{" "}
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTab("login");
                        setAuthError("");
                      }}
                      className="text-[#f97316] hover:underline cursor-pointer font-bold uppercase"
                    >
                      Sign In
                    </button>
                  </div>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={submitting}
                    className="rounded-[2px] font-mono text-xs bg-[#f97316] text-white font-bold uppercase hover:bg-[#ea580c] cursor-pointer"
                  >
                    {submitting ? "REGISTERING…" : "CREATE ACCOUNT"}
                  </Button>
                </CardFooter>
              </form>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
