// Firebase configuration for BuddyBot
import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY || "AIzaSyDEa3i_XLl6fbzPmr1Lm-ZV4Z5xcunu3II",
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN || "buddy-bot-e9b78.firebaseapp.com",
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID || "buddy-bot-e9b78",
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET || "buddy-bot-e9b78.firebasestorage.app",
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID || "1017419855986",
  appId: process.env.REACT_APP_FIREBASE_APP_ID || "1:1017419855986:web:1915163f0b6abaeccdeaeb",
  measurementId: process.env.REACT_APP_FIREBASE_MEASUREMENT_ID || "G-74X31YEEFY",
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase Authentication
export const auth = getAuth(app);

// Google Auth Provider
export const googleProvider = new GoogleAuthProvider();
googleProvider.addScope("email");
googleProvider.addScope("profile");

export default app;
