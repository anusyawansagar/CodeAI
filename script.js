const messages = document.getElementById("messages");
const input = document.getElementById("userInput");
const language = document.getElementById("language");

const BACKEND_URL =
    "https://codeai-backend-0y6t.onrender.com";

let currentUser = null;
let chatHistory = [];
let currentChatId = null;


/* ============================================================
   INITIALIZATION
============================================================ */

async function initializeCodeAI(user) {

    currentUser = user || null;

    if (currentUser) {
        await loadCloudChat();
    } else {
        loadGuestChat();
    }
}


/* ============================================================
   CHAT ID
============================================================ */

function createChatId() {
    return "chat_" + Date.now();
}


/* ============================================================
   GUEST CHAT
============================================================ */

function loadGuestChat() {

    currentChatId = "guest";

    try {
        chatHistory = JSON.parse(
            localStorage.getItem("codeai_guest_chat") || "[]"
        );
    } catch {
        chatHistory = [];
    }

    renderHistory();
}


/* ============================================================
   CLOUD CHAT
============================================================ */

async function loadCloudChat() {

    try {

        const snapshot = await firebaseDB
            .collection("users")
            .doc(currentUser.uid)
            .collection("chats")
            .orderBy("updatedAt", "desc")
            .limit(1)
            .get();

        if (snapshot.empty) {

            currentChatId = createChatId();
            chatHistory = [];

            await saveCloudChat();

        } else {

            const doc = snapshot.docs[0];

            currentChatId = doc.id;

            const data = doc.data();

            chatHistory = Array.isArray(data.messages)
                ? data.messages
                : [];

        }

        renderHistory();

    } catch (error) {

        console.error(
            "Cloud chat loading error:",
            error
        );

        chatHistory = [];

        renderHistory();
    }
}


/* ============================================================
   RENDER HISTORY
============================================================ */

function renderHistory() {

    messages.innerHTML = "";

    if (!chatHistory.length) {

        messages.innerHTML = `
            <div class="welcome">

                <div class="welcome-icon">
                    &lt;/&gt;
                </div>

                <h2>Welcome to CodeAI</h2>

                <p>
                    Ask anything — coding, school, computers,
                    science, writing, technology and more.
                </p>

                <div class="suggestions">

                    <button onclick="useSuggestion('Explain Python loops')">
                        Explain Python loops
                    </button>

                    <button onclick="useSuggestion('Help me debug my code')">
                        Debug my code
                    </button>

                    <button onclick="useSuggestion('Explain this topic simply')">
                        Explain something
                    </button>

                    <button onclick="useSuggestion('Help me build a project')">
                        Build a project
                    </button>

                </div>

            </div>
        `;

        return;
    }

    chatHistory.forEach(message => {

        addMessage(
            message.text,
            message.type,
            false
        );

    });
}


/* ============================================================
   SEND MESSAGE
============================================================ */

async function sendMessage() {

    const text = input.value.trim();

    if (!text) return;

    removeWelcome();

    addMessage(text, "user");

    input.value = "";

    const loadingMessage =
        addMessage("THINKING", "ai");

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

                    history: chatHistory.map(
                        message => ({
                            role:
                                message.type === "user"
                                    ? "user"
                                    : "assistant",

                            content: message.text
                        })
                    )

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
                data.error ||
                "Backend did not return a reply."
            );
        }

        loadingMessage
            .querySelector(".bubble")
            .innerHTML =
            formatAIResponse(data.reply);

        await saveCurrentChat();

    } catch (error) {

        console.error(
            "CODEAI ERROR:",
            error
        );

        loadingMessage
            .querySelector(".bubble")
            .textContent =
            "CodeAI error: " + error.message;
    }
}


/* ============================================================
   ADD MESSAGE
============================================================ */

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

        chatHistory.push({
            text: text,
            type: type
        });

        saveCurrentChat();

    }

    return message;
}


/* ============================================================
   SAVE CHAT
============================================================ */

async function saveCurrentChat() {

    if (!currentUser) {

        localStorage.setItem(
            "codeai_guest_chat",
            JSON.stringify(chatHistory)
        );

        return;
    }

    await saveCloudChat();
}


/* ============================================================
   FIRESTORE SAVE
============================================================ */

async function saveCloudChat() {

    if (!currentUser || !currentChatId) {
        return;
    }

    try {

        await firebaseDB
            .collection("users")
            .doc(currentUser.uid)
            .collection("chats")
            .doc(currentChatId)
            .set(
                {
                    messages: chatHistory,
                    updatedAt:
                        firebase.firestore.FieldValue.serverTimestamp()
                },
                {
                    merge: true
                }
            );

    } catch (error) {

        console.error(
            "Cloud save failed:",
            error
        );
    }
}


/* ============================================================
   REMOVE WELCOME
============================================================ */

function removeWelcome() {

    const welcome =
        document.querySelector(".welcome");

    if (welcome) {
        welcome.remove();
    }
}


/* ============================================================
   FORMAT AI RESPONSE
============================================================ */

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


/* ============================================================
   ESCAPE HTML
============================================================ */

function escapeHTML(text) {

    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


/* ============================================================
   COPY CODE
============================================================ */

function copyCode(button) {

    const code =
        button
            .closest(".code-block")
            .querySelector("code")
            .textContent;

    navigator.clipboard.writeText(code);

    button.textContent =
        "Copied!";

    setTimeout(() => {

        button.textContent =
            "Copy";

    }, 1500);
}


/* ============================================================
   SUGGESTIONS
============================================================ */

function useSuggestion(text) {

    input.value = text;

    input.focus();
}


/* ============================================================
   NEW CHAT
============================================================ */

async function newChat() {

    if (chatHistory.length > 0) {

        if (!confirm(
            "Start a new chat?"
        )) {
            return;
        }
    }

    chatHistory = [];

    if (currentUser) {

        currentChatId =
            createChatId();

        await saveCloudChat();

    } else {

        localStorage.removeItem(
            "codeai_guest_chat"
        );

    }

    renderHistory();
}


/* ============================================================
   ABOUT
============================================================ */

function showAbout() {

    alert(
        "CodeAI\n\n" +
        "A free general AI assistant.\n\n" +
        "Creator:\n" +
        "VARAD WANSAGAR sir created me as a coding agent."
    );
}


/* ============================================================
   ENTER TO SEND
============================================================ */

function handleKey(event) {

    if (
        event.key === "Enter" &&
        !event.shiftKey
    ) {

        event.preventDefault();

        sendMessage();
    }
}