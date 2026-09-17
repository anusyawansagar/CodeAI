const messages = document.getElementById("messages");
const input =
    document.getElementById("userInput") ||
    document.getElementById("messageInput");

const language =
    document.getElementById("language") ||
    document.getElementById("languageSelect");

const BACKEND_URL = "https://codeai-backend-0y6t.onrender.com";

let currentUser = null;
let chatHistory = [];
let currentChatId = null;

let selectedAttachment = null;
let selectedAttachmentType = null;


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

    setupTools();
}


/* ============================================================
   SETUP FILE / CAMERA / MIC BUTTONS
============================================================ */

function setupTools() {

    const attachBtn = document.getElementById("attachBtn");
    const cameraBtn = document.getElementById("cameraBtn");
    const micBtn = document.getElementById("micBtn");

    let fileInput = document.getElementById("fileInput");
    let cameraInput = document.getElementById("cameraInput");

    /*
       Create file input automatically if HTML doesn't have one.
    */

    if (!fileInput) {
        fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.id = "fileInput";
        fileInput.accept = "*/*";
        fileInput.style.display = "none";
        document.body.appendChild(fileInput);
    }

    /*
       Create camera input automatically if HTML doesn't have one.
       capture="environment" asks mobile devices to use the rear camera.
    */

    if (!cameraInput) {
        cameraInput = document.createElement("input");
        cameraInput.type = "file";
        cameraInput.id = "cameraInput";
        cameraInput.accept = "image/*";
        cameraInput.setAttribute("capture", "environment");
        cameraInput.style.display = "none";
        document.body.appendChild(cameraInput);
    }

    if (attachBtn) {
        attachBtn.onclick = () => {
            fileInput.click();
        };
    }

    if (cameraBtn) {
        cameraBtn.onclick = () => {
            cameraInput.click();
        };
    }

    fileInput.onchange = async function () {
        if (this.files && this.files[0]) {
            await handleSelectedFile(this.files[0]);
        }

        this.value = "";
    };

    cameraInput.onchange = async function () {
        if (this.files && this.files[0]) {
            await handleCameraImage(this.files[0]);
        }

        this.value = "";
    };

    if (micBtn) {
        micBtn.onclick = startMicrophone;
    }

    /*
       Remove attachment button
    */

    const removeAttachmentBtn =
        document.getElementById("removeAttachmentBtn");

    if (removeAttachmentBtn) {
        removeAttachmentBtn.onclick = clearAttachment;
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
                <div class="welcome-icon"></div>

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

    /*
       If an image is attached, send it to the vision endpoint.
    */

    if (selectedAttachment &&
        selectedAttachmentType === "image") {

        await sendImageToVision(
            selectedAttachment,
            text || "Analyze this image and tell me what you see."
        );

        return;
    }

    /*
       Normal chat
    */

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

                    language:
                        language
                            ? language.value
                            : "general",

                    history:
                        chatHistory.map(message => ({
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
                data.error ||
                "Backend did not return a reply."
            );
        }

        const bubble =
            loadingMessage.querySelector(".bubble");

        if (bubble) {

            bubble.innerHTML =
                formatAIResponse(data.reply);
        }

        /*
           Save AI response in history.
        */

        chatHistory.push({
            text: data.reply,
            type: "ai"
        });

        await saveCurrentChat();

    } catch (error) {

        console.error(
            "CODEAI ERROR:",
            error
        );

        const bubble =
            loadingMessage.querySelector(".bubble");

        if (bubble) {

            bubble.textContent =
                "CodeAI error: " +
                error.message;
        }
    }
}


/* ============================================================
   HANDLE SELECTED FILE
============================================================ */

async function handleSelectedFile(file) {

    if (!file) return;

    console.log(
        "Selected file:",
        file.name,
        file.type
    );

    /*
       IMAGE
    */

    if (file.type.startsWith("image/")) {

        selectedAttachment = file;
        selectedAttachmentType = "image";

        showAttachmentPreview(
            file,
            "IMAGE"
        );

        return;
    }

    /*
       PDF
    */

    if (
        file.type === "application/pdf" ||
        file.name.toLowerCase().endsWith(".pdf")
    ) {

        await readPDF(file);

        return;
    }

    /*
       TEXT / CODE
    */

    await readTextFile(file);
}


/* ============================================================
   CAMERA IMAGE
============================================================ */

async function handleCameraImage(file) {

    if (!file) return;

    if (!file.type.startsWith("image/")) {

        alert("The camera did not provide an image.");

        return;
    }

    selectedAttachment = file;
    selectedAttachmentType = "image";

    showAttachmentPreview(
        file,
        "CAMERA PHOTO"
    );

    /*
       Automatically ask CodeAI to analyze the photo.
    */

    await sendImageToVision(
        file,
        "Analyze this photo and describe what you can see."
    );
}


/* ============================================================
   IMAGE → VISION
============================================================ */

async function sendImageToVision(
    file,
    question
) {

    if (!file) return;

    removeWelcome();

    /*
       Show image message in chat.
    */

    const imageURL =
        URL.createObjectURL(file);

    const imageMessage =
        document.createElement("div");

    imageMessage.className =
        "message user";

    const imageBubble =
        document.createElement("div");

    imageBubble.className =
        "bubble";

    imageBubble.innerHTML = `
        <div style="font-size:13px;margin-bottom:8px;">
            📷 ${escapeHTML(file.name || "Image")}
        </div>

        <img
            src="${imageURL}"
            style="
                max-width:100%;
                max-height:300px;
                border-radius:12px;
                display:block;
            "
        >

        ${
            question
                ? `<div style="margin-top:8px;">${escapeHTML(question)}</div>`
                : ""
        }
    `;

    imageMessage.appendChild(
        imageBubble
    );

    messages.appendChild(
        imageMessage
    );

    messages.scrollTop =
        messages.scrollHeight;

    /*
       Save user's image request as text.
       We don't save the actual image to Firestore.
    */

    chatHistory.push({
        text:
            `📷 Image: ${file.name || "Image"}\n${question}`,
        type: "user"
    });

    const loadingMessage =
        addMessage(
            "ANALYZING IMAGE...",
            "ai"
        );

    try {

        const dataURL =
            await fileToDataURL(file);

        const response =
            await fetch(
                `${BACKEND_URL}/vision`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        message:
                            question ||
                            "Analyze this image.",

                        image:
                            dataURL
                    })
                }
            );

        const rawResponse =
            await response.text();

        if (!response.ok) {

            throw new Error(
                `Vision backend error ${response.status}: ${rawResponse}`
            );
        }

        let data;

        try {

            data =
                JSON.parse(rawResponse);

        } catch {

            throw new Error(
                "Vision backend returned invalid JSON."
            );
        }

        if (!data.reply) {

            throw new Error(
                data.error ||
                "Vision backend did not return a reply."
            );
        }

        const bubble =
            loadingMessage.querySelector(".bubble");

        if (bubble) {

            bubble.innerHTML =
                formatAIResponse(data.reply);
        }

        /*
           Save AI response.
        */

        chatHistory.push({
            text: data.reply,
            type: "ai"
        });

        await saveCurrentChat();

        clearAttachment();

    } catch (error) {

        console.error(
            "VISION ERROR:",
            error
        );

        const bubble =
            loadingMessage.querySelector(".bubble");

        if (bubble) {

            bubble.textContent =
                "Image analysis error: " +
                error.message;
        }
    }
}


/* ============================================================
   FILE → DATA URL
============================================================ */

function fileToDataURL(file) {

    return new Promise(
        (resolve, reject) => {

            const reader =
                new FileReader();

            reader.onload = () =>
                resolve(reader.result);

            reader.onerror = () =>
                reject(
                    new Error(
                        "Could not read image."
                    )
                );

            reader.readAsDataURL(file);
        }
    );
}


/* ============================================================
   PDF READER
============================================================ */

async function readPDF(file) {

    removeWelcome();

    addMessage(
        `📄 Reading PDF: ${file.name}`,
        "user"
    );

    const loadingMessage =
        addMessage(
            "READING PDF...",
            "ai"
        );

    try {

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );

        const response =
            await fetch(
                `${BACKEND_URL}/read-pdf`,
                {
                    method: "POST",
                    body: formData
                }
            );

        const rawResponse =
            await response.text();

        if (!response.ok) {

            throw new Error(
                `PDF error ${response.status}: ${rawResponse}`
            );
        }

        const data =
            JSON.parse(rawResponse);

        if (!data.success) {

            throw new Error(
                data.error ||
                "PDF could not be read."
            );
        }

        /*
           Put extracted PDF text into chat context.
        */

        const pdfText =
            data.content || "";

        chatHistory.push({
            text:
                `📄 PDF: ${file.name}\n\n${pdfText}`,
            type: "user"
        });

        const bubble =
            loadingMessage.querySelector(
                ".bubble"
            );

        if (bubble) {

            bubble.innerHTML =
                `
                <strong>PDF loaded successfully.</strong>
                <br><br>
                File: ${escapeHTML(file.name)}
                <br>
                Pages: ${data.pages}
                <br>
                Pages with text: ${data.pages_with_text}
                <br><br>
                You can now ask me questions about this PDF.
                `;
        }

        await saveCurrentChat();

    } catch (error) {

        console.error(
            "PDF ERROR:",
            error
        );

        const bubble =
            loadingMessage.querySelector(
                ".bubble"
            );

        if (bubble) {

            bubble.textContent =
                "PDF error: " +
                error.message;
        }
    }
}


/* ============================================================
   TEXT / CODE FILE READER
============================================================ */

async function readTextFile(file) {

    removeWelcome();

    addMessage(
        `📎 Reading file: ${file.name}`,
        "user"
    );

    const loadingMessage =
        addMessage(
            "READING FILE...",
            "ai"
        );

    try {

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );

        const response =
            await fetch(
                `${BACKEND_URL}/read-file`,
                {
                    method: "POST",
                    body: formData
                }
            );

        const rawResponse =
            await response.text();

        if (!response.ok) {

            throw new Error(
                `File error ${response.status}: ${rawResponse}`
            );
        }

        const data =
            JSON.parse(rawResponse);

        if (!data.success) {

            throw new Error(
                data.error ||
                "File could not be read."
            );
        }

        const content =
            data.content || "";

        chatHistory.push({
            text:
                `📎 File: ${file.name}\n\n${content}`,
            type: "user"
        });

        const bubble =
            loadingMessage.querySelector(
                ".bubble"
            );

        if (bubble) {

            bubble.innerHTML =
                `
                <strong>File loaded.</strong>
                <br><br>
                <strong>${escapeHTML(file.name)}</strong>
                <br><br>
                You can now ask me questions about this file.
                `;
        }

        await saveCurrentChat();

    } catch (error) {

        console.error(
            "FILE ERROR:",
            error
        );

        const bubble =
            loadingMessage.querySelector(
                ".bubble"
            );

        if (bubble) {

            bubble.textContent =
                "File error: " +
                error.message;
        }
    }
}


/* ============================================================
   SHOW ATTACHMENT PREVIEW
============================================================ */

function showAttachmentPreview(
    file,
    type
) {

    const preview =
        document.getElementById(
            "attachmentPreview"
        );

    const name =
        document.getElementById(
            "attachmentName"
        );

    const attachmentType =
        document.getElementById(
            "attachmentType"
        );

    if (name) {

        name.textContent =
            file.name;
    }

    if (attachmentType) {

        attachmentType.textContent =
            type;
    }

    if (preview) {

        preview.classList.remove(
            "hidden"
        );

        preview.style.display =
            "flex";
    }
}


/* ============================================================
   CLEAR ATTACHMENT
============================================================ */

function clearAttachment() {

    selectedAttachment = null;
    selectedAttachmentType = null;

    const preview =
        document.getElementById(
            "attachmentPreview"
        );

    if (preview) {

        preview.classList.add(
            "hidden"
        );

        preview.style.display =
            "none";
    }

    const fileInput =
        document.getElementById(
            "fileInput"
        );

    const cameraInput =
        document.getElementById(
            "cameraInput"
        );

    if (fileInput) {
        fileInput.value = "";
    }

    if (cameraInput) {
        cameraInput.value = "";
    }
}


/* ============================================================
   MICROPHONE
============================================================ */

function startMicrophone() {

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {

        alert(
            "Voice input is not supported by this browser."
        );

        return;
    }

    const recognition =
        new SpeechRecognition();

    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = function () {

        console.log(
            "CodeAI microphone started."
        );
    };

    recognition.onresult =
        function (event) {

            let transcript = "";

            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {

                transcript +=
                    event.results[i][0].transcript;
            }

            input.value =
                transcript;
        };

    recognition.onerror =
        function (event) {

            console.error(
                "Microphone error:",
                event.error
            );
        };

    recognition.start();
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
        document.createElement(
            "div"
        );

    message.className =
        `message ${type}`;

    const bubble =
        document.createElement(
            "div"
        );

    bubble.className =
        "bubble";

    if (type === "ai") {

        bubble.innerHTML =
            formatAIResponse(text);

    } else {

        bubble.textContent =
            text;
    }

    message.appendChild(
        bubble
    );

    messages.appendChild(
        message
    );

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

    if (
        !currentUser ||
        !currentChatId
    ) {
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
                    messages:
                        chatHistory,

                    updatedAt:
                        firebase.firestore
                            .FieldValue
                            .serverTimestamp()
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
        document.querySelector(
            ".welcome"
        );

    if (welcome) {

        welcome.remove();
    }
}


/* ============================================================
   FORMAT AI RESPONSE
============================================================ */

function formatAIResponse(text) {

    let output =
        escapeHTML(
            String(text || "")
        );

    /*
       Code blocks
    */

    output =
        output.replace(
            /```([a-zA-Z0-9+#.-]*)\n?([\s\S]*?)```/g,
            function (
                match,
                lang,
                code
            ) {

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

    /*
       Bold text
    */

    output =
        output.replace(
            /\*\*(.*?)\*\*/g,
            "<strong>$1</strong>"
        );

    /*
       Inline code
    */

    output =
        output.replace(
            /`([^`]+)`/g,
            "<code>$1</code>"
        );

    /*
       New lines
    */

    output =
        output.replace(
            /\n/g,
            "<br>"
        );

    return output;
}


/* ============================================================
   ESCAPE HTML
============================================================ */

function escapeHTML(text) {

    return String(text)
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

    navigator.clipboard.writeText(
        code
    );

    button.textContent =
        "Copied!";

    setTimeout(
        () => {
            button.textContent =
                "Copy";
        },
        1500
    );
}


/* ============================================================
   SUGGESTIONS
============================================================ */

function useSuggestion(text) {

    input.value =
        text;

    input.focus();
}


/* ============================================================
   NEW CHAT
============================================================ */

async function newChat() {

    if (chatHistory.length > 0) {

        if (
            !confirm(
                "Start a new chat?"
            )
        ) {
            return;
        }
    }

    chatHistory = [];

    clearAttachment();

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


/* ============================================================
   GLOBAL FUNCTIONS
============================================================ */

window.initializeCodeAI =
    initializeCodeAI;

window.sendMessage =
    sendMessage;

window.handleKey =
    handleKey;

window.newChat =
    newChat;

window.showAbout =
    showAbout;

window.useSuggestion =
    useSuggestion;

window.copyCode =
    copyCode;

window.clearAttachment =
    clearAttachment;