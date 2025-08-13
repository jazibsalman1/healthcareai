
document.getElementById("triageForm").addEventListener("submit", async function (e) {
  e.preventDefault();

  const resultEl = document.getElementById("result");
  const submitBtn = document.getElementById("submitBtn") || document.querySelector('button[type="submit"]');

  // Processing state UI
  resultEl.textContent = "⏳ Processing your request...";
  resultEl.className = "processing";

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Processing...";
  }

  const name = document.getElementById("name").value.trim();
  const age = parseInt(document.getElementById("age").value);
  const symptoms = document.getElementById("symptoms").value.trim();

  // Client-side validation
  if (!name || name.length > 50) return showError("Please enter a valid name (1–50 characters)");
  if (!age || age <= 0 || age >= 120) return showError("Please enter a valid age (1–119)");
  if (!symptoms || symptoms.length < 5 || symptoms.length > 500)
    return showError("Please describe symptoms (5–500 characters)");

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

    const response = await fetch("/api/triage_stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/plain",
      },
      body: JSON.stringify({ name, age, symptoms }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
    }

    // Prepare for streaming
    resultEl.textContent = "";
    resultEl.className = "streaming";

    const typingIndicator = document.createElement("span");
    typingIndicator.className = "typing-indicator";
    typingIndicator.textContent = "💭 AI is thinking...";
    resultEl.appendChild(typingIndicator);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let advice = "";
    let isFirstChunk = true;

    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      advice += chunk;

      if (isFirstChunk && chunk.trim()) {
        typingIndicator.remove();
        resultEl.className = "response";
        isFirstChunk = false;
      }

      if (!isFirstChunk) {
        resultEl.textContent = advice;
        resultEl.scrollTop = resultEl.scrollHeight; // Auto-scroll
      }
    }

    // Finalize response
    if (advice.trim()) {
      resultEl.className = "response complete";
      const completionIndicator = document.createElement("div");
      completionIndicator.className = "completion-indicator";
      completionIndicator.innerHTML = "✅ <small>Response complete</small>";
      resultEl.appendChild(completionIndicator);
    } else {
      showError("No response received from the AI model");
    }
  } catch (err) {
    if (err.name === "AbortError") {
      showError("Request timed out. Please try again with shorter symptoms description.");
    } else {
      showError(`Error: ${err.message}`);
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Get Medical Advice";
    }
  }

  function showError(message) {
    resultEl.textContent = message;
    resultEl.className = "error";

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Get Medical Advice";
    }
  }
});

// Health check function
async function checkModelHealth() {
  try {
    const response = await fetch("/api/health");
    if (response.ok) {
      const data = await response.json();
      console.log("Model status:", data);
      return true;
    }
  } catch (err) {
    console.warn("Health check failed:", err);
  }
  return false;
}

// Page load logic
document.addEventListener("DOMContentLoaded", function () {
  checkModelHealth().then((isHealthy) => {
    if (!isHealthy) console.warn("AI model may not be ready");
  });

  // Remove error styles on input change
  document.querySelectorAll("#triageForm input, #triageForm textarea").forEach((input) => {
    input.addEventListener("input", function () {
      this.classList.remove("error");
    });
  });
});

// Utility for validation
function validateInput(element, condition, errorMessage) {
  if (!condition) {
    element.classList.add("error");
    element.title = errorMessage;
    return false;
  }
  element.classList.remove("error");
  element.title = "";
  return true;
}
