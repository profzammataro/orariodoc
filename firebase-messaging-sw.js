// firebase-messaging-sw.js
// Service Worker per Firebase Cloud Messaging

importScripts('https://www.gstatic.com/firebasejs/10.12.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyCfOWXLUuDcdVF4TdXCk_TOTOXZ9sbipyw",
  authDomain: "orariodoc.firebaseapp.com",
  projectId: "orariodoc",
  storageBucket: "orariodoc.firebasestorage.app",
  messagingSenderId: "902585792846",
  appId: "1:902585792846:web:fbb2f95b27dd02734d461f"
});

const messaging = firebase.messaging();

// Gestisce le notifiche quando l'app è in background
messaging.onBackgroundMessage(payload => {
  console.log('[SW] Messaggio in background ricevuto:', payload);
  const { title, body } = payload.notification;
  self.registration.showNotification(title, {
    body,
    icon: '/orariodoc/icon-192.png',
    badge: '/orariodoc/icon-192.png',
    vibrate: [200, 100, 200],
    tag: 'orariodoc-notifica',   // sostituisce notifiche precedenti
    renotify: true
  });
});
