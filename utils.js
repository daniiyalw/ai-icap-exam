// utils.js
export function getUserMode() {
  return localStorage.getItem("mode") || "demo";
}

export function getUserToken() {
  return localStorage.getItem("token");
}

export async function verifyAccess(chapter) {
  const mode = getUserMode();
  const token = getUserToken();
  
  if (mode === "demo") {
    return chapter === 1;
  }
  
  try {
    const response = await fetch("http://127.0.0.1:5000/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, chapter })
    });
    const data = await response.json();
    return data.valid;
  } catch (error) {
    console.error("Verification failed:", error);
    return false;
  }
}