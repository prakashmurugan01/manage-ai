import { Camera, CheckCircle2, RotateCcw, ShieldCheck, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "../ui/Button.jsx";

function canvasToBlob(canvas) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
}

export default function FaceCapture({ email, mode = "login", onSubmit }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [captures, setCaptures] = useState([]);

  const steps = mode === "enroll" ? ["Front", "Left", "Right"] : ["Live"];

  useEffect(() => () => stopCamera(), []);

  async function startCamera() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      setActive(true);
    } catch {
      setError("Camera permission is required for face unlock.");
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks?.().forEach((track) => track.stop());
    streamRef.current = null;
    setActive(false);
  }

  async function capture() {
    if (!videoRef.current) return;
    setBusy(true);
    setError("");
    try {
      const canvas = document.createElement("canvas");
      canvas.width = videoRef.current.videoWidth || 640;
      canvas.height = videoRef.current.videoHeight || 480;
      canvas.getContext("2d").drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const blob = await canvasToBlob(canvas);
      if (mode === "enroll") {
        setCaptures((items) => [...items, blob].slice(0, 3));
        return;
      }
      const formData = new FormData();
      if (email) formData.append("email", email);
      formData.append("enabled", "true");
      formData.append("image", blob, "face-capture.jpg");
      await onSubmit(formData);
      stopCamera();
    } catch (caught) {
      setError(caught?.response?.data?.detail || "Face capture failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submitEnrollment() {
    setBusy(true);
    setError("");
    try {
      const formData = new FormData();
      if (email) formData.append("email", email);
      formData.append("enabled", "true");
      captures.forEach((blob, index) => formData.append("face_images", blob, `face-${index + 1}.jpg`));
      await onSubmit(formData);
      setCaptures([]);
      stopCamera();
    } catch (caught) {
      setError(caught?.response?.data?.detail || "Face enrollment failed.");
    } finally {
      setBusy(false);
    }
  }

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const formData = new FormData();
      if (email) formData.append("email", email);
      formData.append("enabled", "true");
      formData.append("image", file);
      await onSubmit(formData);
    } catch (caught) {
      setError(caught?.response?.data?.detail || "Face image upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
      <div className="mb-3 grid grid-cols-3 gap-2">
        {steps.map((step, index) => (
          <div key={step} className={`rounded-lg border px-2 py-2 text-center text-xs ${captures[index] || mode === "login" ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-200" : "border-white/10 bg-white/[0.035] text-slate-400"}`}>
            {captures[index] ? <CheckCircle2 size={14} className="mx-auto mb-1" /> : null}
            {step}
          </div>
        ))}
      </div>
      <div className="overflow-hidden rounded-lg border border-white/10 bg-black/30">
        <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full object-cover" />
      </div>
      {error && <p className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-200">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {!active && <Button variant="secondary" onClick={startCamera}><Camera size={16} />Camera</Button>}
        {active && mode === "enroll" && captures.length < 3 && <Button onClick={capture} disabled={busy}><ShieldCheck size={16} />Capture {steps[captures.length]}</Button>}
        {active && mode === "enroll" && captures.length > 0 && <Button variant="secondary" onClick={() => setCaptures([])} disabled={busy}><RotateCcw size={16} />Retake</Button>}
        {mode === "enroll" && captures.length === 3 && <Button onClick={submitEnrollment} disabled={busy}><ShieldCheck size={16} />Enroll face</Button>}
        {active && mode !== "enroll" && <Button onClick={capture} disabled={busy}><ShieldCheck size={16} />Unlock</Button>}
        <label className="btn-secondary inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/15">
          <Upload size={16} />
          Upload
          <input type="file" accept="image/*" className="hidden" onChange={upload} />
        </label>
      </div>
    </div>
  );
}
