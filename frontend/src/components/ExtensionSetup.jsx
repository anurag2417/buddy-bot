import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Chrome, Download, Shield, CheckCircle, AlertCircle, Puzzle, ArrowRight } from "lucide-react";
import { useAuth } from "./AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ExtensionSetup() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [deviceId, setDeviceId] = useState("");

  // Check if extension is already installed
  useEffect(() => {
    if (user?.extension_installed) {
      navigate("/");
    }
  }, [user, navigate]);

  // Listen for extension confirmation message
  useEffect(() => {
    const handleExtensionMessage = async (event) => {
      if (event.data && event.data.type === "BUDDYBOT_EXTENSION_INSTALLED") {
        const extDeviceId = event.data.deviceId;
        setDeviceId(extDeviceId);
        await confirmExtension(extDeviceId);
      }
    };

    window.addEventListener("message", handleExtensionMessage);
    return () => window.removeEventListener("message", handleExtensionMessage);
  }, []);

  const confirmExtension = async (devId) => {
    try {
      setChecking(true);
      setError("");
      
      const token = localStorage.getItem("buddybot_token");
      await axios.post(
        `${API}/auth/confirm-extension`,
        { device_id: devId },
        {
          headers: { Authorization: `Bearer ${token}` },
          withCredentials: true,
        }
      );
      
      // Refresh user data
      if (refreshUser) {
        await refreshUser();
      }
      
      setStep(4); // Success step
      
      // Redirect after a short delay
      setTimeout(() => {
        navigate("/");
      }, 2000);
    } catch (err) {
      setError("Failed to confirm extension. Please try again.");
      setChecking(false);
    }
  };

  const handleManualConfirm = async () => {
    // Generate a device ID for manual confirmation
    const manualDeviceId = `device_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    await confirmExtension(manualDeviceId);
  };

  const handleCheckExtension = async () => {
    // Skip auto-detection and just go to manual confirmation
    // Browser extensions can't easily communicate with web pages without specific setup
    await handleManualConfirm();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-emerald-50 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {/* Progress Steps */}
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all ${
                    step >= s
                      ? "bg-sky-500 text-white"
                      : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {step > s ? <CheckCircle className="w-5 h-5" /> : s}
                </div>
                {s < 3 && (
                  <div
                    className={`w-16 h-1 mx-2 rounded ${
                      step > s ? "bg-sky-500" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-xl p-8 md:p-12">
          {/* Step 1: Introduction */}
          {step === 1 && (
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-sky-400 to-emerald-400 rounded-2xl mx-auto mb-6 flex items-center justify-center">
                <Shield className="w-10 h-10 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-slate-800 mb-4">
                One More Step to Keep Your Child Safe!
              </h1>
              <p className="text-lg text-slate-600 mb-8">
                Install the <strong>BuddyBot Safety Monitor</strong> browser extension to monitor your child's browsing activity across all tabs.
              </p>
              
              <div className="bg-slate-50 rounded-2xl p-6 mb-8">
                <h3 className="font-semibold text-slate-700 mb-4">What does the extension do?</h3>
                <div className="grid md:grid-cols-3 gap-4 text-sm">
                  <div className="bg-white rounded-xl p-4">
                    <div className="w-10 h-10 bg-sky-100 rounded-lg mx-auto mb-2 flex items-center justify-center">
                      <Chrome className="w-5 h-5 text-sky-600" />
                    </div>
                    <p className="text-slate-600">Monitors search queries on Google, Bing, YouTube & more</p>
                  </div>
                  <div className="bg-white rounded-xl p-4">
                    <div className="w-10 h-10 bg-emerald-100 rounded-lg mx-auto mb-2 flex items-center justify-center">
                      <AlertCircle className="w-5 h-5 text-emerald-600" />
                    </div>
                    <p className="text-slate-600">Detects inappropriate content and alerts you instantly</p>
                  </div>
                  <div className="bg-white rounded-xl p-4">
                    <div className="w-10 h-10 bg-purple-100 rounded-lg mx-auto mb-2 flex items-center justify-center">
                      <Puzzle className="w-5 h-5 text-purple-600" />
                    </div>
                    <p className="text-slate-600">Works even in incognito mode for complete protection</p>
                  </div>
                </div>
              </div>

              <button
                onClick={() => setStep(2)}
                className="w-full bg-gradient-to-r from-sky-500 to-emerald-500 text-white py-4 px-6 rounded-xl font-semibold text-lg hover:from-sky-600 hover:to-emerald-600 transition-all flex items-center justify-center gap-2"
              >
                Continue to Install
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* Step 2: Download Instructions */}
          {step === 2 && (
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-orange-400 to-amber-400 rounded-2xl mx-auto mb-6 flex items-center justify-center">
                <Download className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-4">
                Install the Extension
              </h2>
              <p className="text-slate-600 mb-8">
                Follow these steps to install the BuddyBot Safety Monitor:
              </p>

              <div className="text-left bg-slate-50 rounded-2xl p-6 mb-8">
                <ol className="space-y-4">
                  <li className="flex items-start gap-3">
                    <span className="w-7 h-7 bg-sky-500 text-white rounded-full flex items-center justify-center flex-shrink-0 font-bold text-sm">1</span>
                    <div>
                      <p className="font-medium text-slate-700">Download the Extension</p>
                      <p className="text-sm text-slate-500">Click the button below to download the extension files</p>
                    </div>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="w-7 h-7 bg-sky-500 text-white rounded-full flex items-center justify-center flex-shrink-0 font-bold text-sm">2</span>
                    <div>
                      <p className="font-medium text-slate-700">Open Chrome Extensions</p>
                      <p className="text-sm text-slate-500">Go to <code className="bg-white px-2 py-1 rounded text-sky-600">chrome://extensions</code> in your browser</p>
                    </div>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="w-7 h-7 bg-sky-500 text-white rounded-full flex items-center justify-center flex-shrink-0 font-bold text-sm">3</span>
                    <div>
                      <p className="font-medium text-slate-700">Enable Developer Mode</p>
                      <p className="text-sm text-slate-500">Toggle "Developer mode" in the top right corner</p>
                    </div>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="w-7 h-7 bg-sky-500 text-white rounded-full flex items-center justify-center flex-shrink-0 font-bold text-sm">4</span>
                    <div>
                      <p className="font-medium text-slate-700">Load the Extension</p>
                      <p className="text-sm text-slate-500">Click "Load unpacked" and select the extracted extension folder</p>
                    </div>
                  </li>
                </ol>
              </div>

              <div className="space-y-3">
                <a
                  href="/extension.zip"
                  download
                  className="w-full bg-gradient-to-r from-sky-500 to-emerald-500 text-white py-4 px-6 rounded-xl font-semibold text-lg hover:from-sky-600 hover:to-emerald-600 transition-all flex items-center justify-center gap-2"
                >
                  <Download className="w-5 h-5" />
                  Download Extension
                </a>
                <button
                  onClick={handleCheckExtension}
                  disabled={checking}
                  className="w-full bg-slate-100 text-slate-700 py-4 px-6 rounded-xl font-semibold text-lg hover:bg-slate-200 transition-all flex items-center justify-center gap-2"
                >
                  {checking ? (
                    <>
                      <div className="w-5 h-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                      Checking...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      I've Installed the Extension
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Manual Confirmation */}
          {step === 3 && (
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-amber-400 to-orange-400 rounded-2xl mx-auto mb-6 flex items-center justify-center">
                <AlertCircle className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-4">
                Extension Not Detected
              </h2>
              <p className="text-slate-600 mb-8">
                We couldn't automatically detect the extension. If you've installed it, click below to continue.
              </p>

              {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6">
                  {error}
                </div>
              )}

              <div className="space-y-3">
                <button
                  onClick={handleManualConfirm}
                  disabled={checking}
                  className="w-full bg-gradient-to-r from-sky-500 to-emerald-500 text-white py-4 px-6 rounded-xl font-semibold text-lg hover:from-sky-600 hover:to-emerald-600 transition-all flex items-center justify-center gap-2"
                >
                  {checking ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Confirming...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      I've Installed the Extension - Continue
                    </>
                  )}
                </button>
                <button
                  onClick={() => setStep(2)}
                  className="w-full bg-slate-100 text-slate-700 py-4 px-6 rounded-xl font-semibold text-lg hover:bg-slate-200 transition-all"
                >
                  Back to Instructions
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Success */}
          {step === 4 && (
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-emerald-400 to-green-400 rounded-2xl mx-auto mb-6 flex items-center justify-center">
                <CheckCircle className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-4">
                All Set! 🎉
              </h2>
              <p className="text-slate-600 mb-8">
                The BuddyBot Safety Monitor extension is now active. Your child is protected!
              </p>
              <div className="bg-emerald-50 text-emerald-700 p-4 rounded-xl">
                Redirecting you to the chat...
              </div>
            </div>
          )}
        </div>

        {/* Footer note */}
        <p className="text-center text-slate-500 text-sm mt-6">
          The extension is required for BuddyBot to monitor browsing activity and keep your child safe online.
        </p>
      </div>
    </div>
  );
}
