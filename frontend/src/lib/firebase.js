import { initializeApp } from "firebase/app";
import { getAnalytics, isSupported as isAnalyticsSupported } from "firebase/analytics";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyCiuXcEM9RuFBM1nEHBCpn19hShaeJ1Wyo",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "manage-d7841.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "manage-d7841",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "manage-d7841.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "185772558814",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:185772558814:web:419b5844779d6cf09af54f",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-N3YH8PVSYH",
};

export const firebaseApp = initializeApp(firebaseConfig);
export const firestore = getFirestore(firebaseApp);

export const analyticsPromise =
  typeof window === "undefined"
    ? Promise.resolve(null)
    : isAnalyticsSupported()
        .then((supported) => (supported ? getAnalytics(firebaseApp) : null))
        .catch(() => null);
