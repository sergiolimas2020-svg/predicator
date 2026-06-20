(function () {
  const mount = document.getElementById("ai-chat-root");
  if (!mount) return;

  mount.innerHTML = `
    <section class="ai-chat-panel">
      <div class="ai-chat-head">
        <div>
          <strong>Chat de analisis</strong>
          <span>Beta gratis con datos internos de PREDIKTOR</span>
        </div>
        <a href="/plan-pro">Pro</a>
      </div>
      <div class="ai-chat-log" aria-live="polite">
        <div class="ai-chat-msg ai-chat-bot">Preguntame por corners, tiros a puerta, remates de jugador, ganador, DNB u Over 1.5 goles. Ejemplo: "Que piensas del Over 1.5 tiros a puerta de Alexander Isak?"</div>
      </div>
      <div class="ai-chat-examples" aria-label="Ejemplos de preguntas">
        <button class="ai-chat-example" type="button">Over 1.5 en Netherlands vs Sweden</button>
        <button class="ai-chat-example" type="button">Over 6.5 corners entre Ecuador y Curacao</button>
        <button class="ai-chat-example" type="button">Over 1.5 tiros a puerta de Alexander Isak</button>
        <button class="ai-chat-example" type="button">Over 2.5 remates de Raul Jimenez</button>
        <button class="ai-chat-example" type="button">Ecuador gol primera mitad vs Curacao</button>
      </div>
      <form class="ai-chat-form">
        <textarea name="message" rows="2" maxlength="1200" placeholder="Ej: Over 1.5 tiros a puerta de Alexander Isak"></textarea>
        <button type="submit">Preguntar</button>
      </form>
      <div class="ai-chat-foot">Modo gratis: usa archivos internos de PREDIKTOR, sin consumir OpenAI.</div>
    </section>
  `;

  const form = mount.querySelector(".ai-chat-form");
  const log = mount.querySelector(".ai-chat-log");
  const textarea = mount.querySelector("textarea");
  const submit = mount.querySelector('button[type="submit"]');
  const foot = mount.querySelector(".ai-chat-foot");

  function appendMessage(text, type) {
    const message = document.createElement("div");
    message.className = `ai-chat-msg ai-chat-${type}`;
    message.textContent = text;
    log.appendChild(message);
    log.scrollTop = log.scrollHeight;
  }

  function ask(text) {
    textarea.value = text;
    form.requestSubmit();
  }

  mount.querySelectorAll(".ai-chat-example").forEach((button) => {
    button.addEventListener("click", () => ask(button.textContent.trim()));
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = textarea.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    textarea.value = "";
    submit.disabled = true;
    submit.textContent = "Analizando";

    try {
      const response = await fetch("/api/ai-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      });
      const data = await response.json();

      if (data.locked) {
        appendMessage(data.error, "bot");
        foot.innerHTML = '<a href="/plan-pro">Activar PREDIKTOR Pro</a>';
        return;
      }
      if (!response.ok) throw new Error(data.error || "No se pudo responder.");

      appendMessage(data.answer, "bot");
      foot.textContent = data.free_data_mode
        ? "Modo gratis: respuesta generada con datos internos, sin consumir OpenAI."
        : "Respuesta generada.";
    } catch (error) {
      appendMessage(error.message || "No se pudo responder.", "bot");
    } finally {
      submit.disabled = false;
      submit.textContent = "Preguntar";
    }
  });
}());
