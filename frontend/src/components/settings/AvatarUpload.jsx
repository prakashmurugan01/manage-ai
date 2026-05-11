import { Upload, Camera, X, CheckCircle, Loader } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../../api/client.js";
import { useAuth } from "../../context/AuthContext.jsx";

export default function AvatarUpload({ onUploadComplete }) {
  const { user, updateUserData } = useAuth();
  const fileInputRef = useRef(null);
  const [preview, setPreview] = useState(user?.avatar || null);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (user?.avatar) {
      setPreview(user.avatar);
    }
  }, [user?.avatar]);

  const handleFile = async (file) => {
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
      setError("Please upload an image file");
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      setError("Image must be less than 5MB");
      return;
    }

    // Preview
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target.result);
    reader.readAsDataURL(file);

    // Upload
    await uploadAvatar(file);
  };

  const uploadAvatar = async (file) => {
    try {
      setUploading(true);
      setError(null);

      const formData = new FormData();
      formData.append("avatar", file);

      // Update user profile with new avatar
      const response = await api.patch("/api/users/me/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      updateUserData?.(response.data);
      setSuccess(true);
      onUploadComplete?.(response.data);

      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to upload avatar");
      setPreview(user?.avatar || null);
    } finally {
      setUploading(false);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFile(files[0]);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Premium Avatar Container */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-8">
        {/* Animated Background */}
        <div className="pointer-events-none absolute inset-0">
          {/* Gradient Animation */}
          <div className="animated-gradient absolute inset-0 opacity-30" />
          
          {/* Floating Orbs */}
          <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-purple-500/20 blur-3xl animate-pulse" />
          <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-blue-500/20 blur-3xl animate-pulse animation-delay-2000" />
          <div className="absolute top-1/2 left-1/2 h-60 w-60 rounded-full bg-pink-500/20 blur-3xl animate-pulse animation-delay-4000 -translate-x-1/2 -translate-y-1/2" />
        </div>

        {/* Content */}
        <div className="relative z-10 flex flex-col items-center gap-6">
          {/* Avatar Display */}
          <div
            className={`relative h-40 w-40 rounded-full overflow-hidden ring-4 ring-purple-500/50 transition-all duration-500 ${
              uploading ? "scale-95 opacity-70" : "scale-100 opacity-100"
            }`}
          >
            {preview ? (
              <>
                {/* Animated Background Behind Avatar */}
                <div className="absolute inset-0 bg-gradient-to-br from-purple-600 via-blue-600 to-pink-600 animate-gradient" />
                
                {/* Avatar Image */}
                <img
                  src={typeof preview === "string" && preview.startsWith("data:")
                    ? preview
                    : `${process.env.REACT_APP_API_URL || "http://localhost:8000"}${preview}`}
                  alt="User Avatar"
                  className="relative h-full w-full object-cover"
                />

                {/* Overlay Gradient */}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/30 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-300" />
              </>
            ) : (
              <>
                <div className="absolute inset-0 bg-gradient-to-br from-purple-600 via-blue-600 to-pink-600 animate-gradient" />
                <div className="relative h-full w-full flex items-center justify-center">
                  <Camera size={48} className="text-white/80" />
                </div>
              </>
            )}

            {/* Loading Spinner */}
            {uploading && (
              <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center">
                <Loader size={32} className="text-white animate-spin" />
              </div>
            )}

            {/* Success Checkmark */}
            {success && (
              <div className="absolute inset-0 bg-green-500/80 flex items-center justify-center animate-pulse">
                <CheckCircle size={48} className="text-white" />
              </div>
            )}
          </div>

          {/* User Info */}
          <div className="text-center">
            <h3 className="text-2xl font-bold text-white">
              {user?.full_name || user?.email}
            </h3>
            <p className="text-sm text-slate-400">Update your profile picture</p>
          </div>

          {/* Upload Area */}
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`w-full max-w-sm rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-300 ${
              dragActive
                ? "border-purple-400 bg-purple-500/20 scale-105"
                : "border-slate-500 hover:border-purple-400 hover:bg-purple-500/10"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileInput}
              className="hidden"
              disabled={uploading}
            />

            <div className="flex flex-col items-center gap-3">
              <div className={`p-3 rounded-full transition-all ${
                dragActive
                  ? "bg-purple-500/30"
                  : "bg-slate-700 group-hover:bg-purple-500/20"
              }`}>
                <Upload
                  size={24}
                  className={`${dragActive ? "text-purple-300" : "text-slate-400"}`}
                />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">
                  {dragActive ? "Drop image here" : "Drag and drop or click"}
                </p>
                <p className="text-xs text-slate-400">
                  PNG, JPG, GIF up to 5MB
                </p>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="w-full max-w-sm rounded-lg bg-red-500/20 border border-red-500/30 p-3">
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="w-full max-w-sm rounded-lg bg-green-500/20 border border-green-500/30 p-3 animate-fade-in">
              <p className="text-sm text-green-300 flex items-center gap-2">
                <CheckCircle size={16} />
                Avatar updated successfully!
              </p>
            </div>
          )}

          {/* Info */}
          <div className="max-w-sm text-center">
            <p className="text-xs text-slate-400">
              📷 Your avatar appears across the platform in messages, profiles, and collaboration areas.
            </p>
          </div>
        </div>
      </div>

      {/* Avatar Preview Backgrounds */}
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-white">Available Background Styles</h4>
        <div className="grid grid-cols-4 gap-3">
          {[
            { name: "Gradient 1", colors: "from-purple-600 via-blue-600 to-pink-600" },
            { name: "Gradient 2", colors: "from-emerald-600 via-cyan-600 to-blue-600" },
            { name: "Gradient 3", colors: "from-orange-600 via-red-600 to-pink-600" },
            { name: "Gradient 4", colors: "from-indigo-600 via-purple-600 to-rose-600" },
          ].map((gradient, idx) => (
            <div
              key={idx}
              className={`h-20 rounded-lg bg-gradient-to-br ${gradient.colors} border-2 border-slate-700 hover:border-purple-400 transition-all cursor-pointer transform hover:scale-105`}
              title={gradient.name}
            />
          ))}
        </div>
      </div>

      {/* CSS for animations */}
      <style>{`
        @keyframes animate-gradient {
          0%, 100% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
        }

        .animate-gradient {
          background-size: 200% 200%;
          animation: animate-gradient 15s ease infinite;
        }

        .animated-grid {
          background-image:
            linear-gradient(0deg, transparent 24%, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(255, 255, 255, 0.05) 75%, rgba(255, 255, 255, 0.05) 76%, transparent 77%, transparent),
            linear-gradient(90deg, transparent 24%, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(255, 255, 255, 0.05) 75%, rgba(255, 255, 255, 0.05) 76%, transparent 77%, transparent);
          background-size: 50px 50px;
        }

        .animation-delay-2000 {
          animation-delay: 2s;
        }

        .animation-delay-4000 {
          animation-delay: 4s;
        }

        .animate-fade-in {
          animation: fadeIn 0.3s ease-in;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
