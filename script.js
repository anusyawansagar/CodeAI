const messages = document.getElementById("messages");
const input = document.getElementById("userInput");
const language = document.getElementById("language");

const BACKEND_URL = "https://codeai-backend-0y6t.onrender.com";

let chatHistory = JSON.parse(
    localStorage.getItem("codeai_history") || "[]"
);


/* LOAD SAVED CHAT */

window.addEventListener("DOMContentLoaded", () => {

    if (chatHistory.length > 0) {

        const welcome = document.querySelector(".welcome");

        if (welcome) {
            welcome.remove();
        }

        chatHistory.forEach(message => {

            addMessage(
                message.text,
                message.type,
                false
            );

        });

    }

});


/* SEND MESSAGE */

async function sendMessage() {

    const text = input.value.trim();

    if (!text) return;

    const welcome = document.querySelector(".welcome");

    if (welcome) {
        welcome.remove();
    }

    addMessage(text, "user");

    input.value = "";

    const loadingMessage =
        addMessage("Thinking... 🤖", "ai");


    try {

        const response = await fetch(
            `${BACKEND_URL}/chat`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    message: text,

                    language: language.value,

                    history: chatHistory.map(message => ({

                        role:
                            message.type === "user"
                                ? "user"
                                : "assistant",

                        content: message.text

                    }))

                })

            }
        );


        const rawResponse =
            await response.text();


        if (!response.ok) {

            throw new Error(
                `Backend error ${response.status}: ${rawResponse}`
            );

        }


        let data;

        try {

            data = JSON.parse(rawResponse);

        } catch {

            throw new Error(
                "Backend returned invalid JSON."
            );

        }


        if (!data.reply) {

            throw new Error(
                "Backend did not return a reply."
            );

        }


        loadingMessage
            .querySelector(".bubble")
            .innerHTML =
            formatAIResponse(data.reply);


        saveChatHistory();


    } catch (error) {

        console.error(
            "CODEAI ERROR:",
            error
        );


        loadingMessage
            .querySelector(".bubble")
            .textContent =
            "❌ " + error.message;

    }

}


/* ADD MESSAGE */

function addMessage(
    text,
    type,
    save = true
) {

    const message =
        document.createElement("div");

    message.className =
        `message ${type}`;


    const bubble =
        document.createElement("div");

    bubble.className = "bubble";


    if (type === "ai") {

        bubble.innerHTML =
            formatAIResponse(text);

    } else {

        bubble.textContent = text;

    }


    message.appendChild(bubble);

    messages.appendChild(message);


    messages.scrollTop =
        messages.scrollHeight;


    if (save) {
        saveChatHistory();
    }


    return message;

}


/* SAVE CHAT */

function saveChatHistory() {

    const allMessages =
        messages.querySelectorAll(".message");


    chatHistory = [];


    allMessages.forEach(message => {

        const bubble =
            message.querySelector(".bubble");


        if (!bubble) return;


        chatHistory.push({

            text: bubble.innerText,

            type:
                message.classList.contains("user")
                    ? "user"
                    : "ai"

        });

    });


    localStorage.setItem(
        "codeai_history",
        JSON.stringify(chatHistory)
    );

}


/* FORMAT AI RESPONSE */

function formatAIResponse(text) {

    text = escapeHTML(text);


    text = text.replace(
        /```([a-zA-Z0-9+#.-]*)\n?([\s\S]*?)```/g,

        function(match, lang, code) {

            return `

                <div class="code-block">

                    <div class="code-header">

                        <span>
                            ${lang || "code"}
                        </span>

                        <button
                            class="copy-code"
                            onclick="copyCode(this)"
                        >
                            Copy
                        </button>

                    </div>

                    <pre><code>${code.trim()}</code></pre>

                </div>

            `;

        }
    );


    text = text.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );


    text = text.replace(
        /\n/g,
        "<br>"
    );


    return text;

}


/* ESCAPE HTML */

function escapeHTML(text) {

    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


/* COPY CODE */

function copyCode(button) {

    const code =
        button
            .closest(".code-block")
            .querySelector("code")
            .textContent;


    navigator.clipboard.writeText(code);


    button.textContent = "Copied!";


    setTimeout(() => {

        button.textContent = "Copy";

    }, 1500);

}


/* SUGGESTIONS */

function useSuggestion(text) {

    input.value = text;

    input.focus();

}


/* NEW CHAT */

function newChat() {

    if (chatHistory.length > 0) {

        if (!confirm(
            "Start a new chat? The current chat will be cleared."
        )) {
            return;
        }

    }


    chatHistory = [];

    localStorage.removeItem(
        "codeai_history"
    );


    location.reload();

}


/* ENTER */

function handleKey(event) {

    if (
        event.key === "Enter" &&
        !event.shiftKey
    ) {

        event.preventDefault();

        sendMessage();

    }

}