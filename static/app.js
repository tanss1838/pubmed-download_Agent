document.addEventListener("DOMContentLoaded", () => {
    const searchForm = document.getElementById("search-form");
    const keywordInput = document.getElementById("keyword");
    const countInput = document.getElementById("count");
    const submitBtn = document.getElementById("submit-btn");
    const consoleOutput = document.getElementById("console-output");
    const libraryList = document.getElementById("library-list");
    const statTotal = document.getElementById("stat-total");
    const libraryFilter = document.getElementById("library-filter");

    let eventSource = null;
    let pollInterval = null;
    let loadedPapers = [];

    // Initialize layout
    fetchPapers();

    // SSE Connection for Live Logs
    function connectToLogStream() {
        if (eventSource) {
            eventSource.close();
        }

        appendConsoleLine("🔌 Connecting to agent log stream...", "system-line");
        eventSource = new EventSource("/api/logs");

        eventSource.onmessage = (event) => {
            const data = event.data;
            
            // Format console lines based on content
            let type = "system-line";
            if (data.includes("✅") || data.includes("✓")) {
                type = "success-line";
            } else if (data.includes("❌") || data.includes("⚠️")) {
                type = "error-line";
            }

            appendConsoleLine(data, type);

            // Trigger list refresh when a paper completes downloading
            if (data.includes("✅ Download complete!")) {
                fetchPapers();
            }

            // Close connection when agent run completes
            if (data.includes("🏁 AI Agent run completed.") || data.includes("Critical Agent Error")) {
                stopAgentUI();
            }
        };

        eventSource.onerror = (err) => {
            appendConsoleLine("⚠️ Lost connection to log stream.", "error-line");
            if (eventSource) {
                eventSource.close();
            }
        };
    }

    function appendConsoleLine(text, type = "system-line") {
        const line = document.createElement("div");
        line.className = `console-line ${type}`;
        line.textContent = text;
        consoleOutput.appendChild(line);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    // Start Search Agent
    searchForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const keyword = keywordInput.value.trim();
        const count = parseInt(countInput.value);

        if (!keyword) return;

        // Reset UI status
        submitBtn.disabled = true;
        submitBtn.classList.add("loading");
        submitBtn.querySelector(".btn-text").textContent = "Agent Working...";
        submitBtn.querySelector(".btn-icon").setAttribute("data-lucide", "loader-2");
        lucide.createIcons();

        consoleOutput.innerHTML = "";
        appendConsoleLine(`🚀 Starting new AI Agent research for: "${keyword}"...`, "system-line");

        try {
            const response = await fetch("/api/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ keyword, count })
            });

            const result = await response.json();
            if (result.success) {
                connectToLogStream();
                // Start polling library results periodically
                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(fetchPapers, 4000);
            } else {
                appendConsoleLine(`❌ Error: ${result.error}`, "error-line");
                submitBtn.disabled = false;
                submitBtn.classList.remove("loading");
                submitBtn.querySelector(".btn-text").textContent = "Start Research Agent";
            }
        } catch (error) {
            appendConsoleLine(`❌ Connection Failure: ${error.message}`, "error-line");
            submitBtn.disabled = false;
            submitBtn.classList.remove("loading");
            submitBtn.querySelector(".btn-text").textContent = "Start Research Agent";
        }
    });

    function stopAgentUI() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }

        submitBtn.disabled = false;
        submitBtn.classList.remove("loading");
        submitBtn.querySelector(".btn-text").textContent = "Start Research Agent";
        submitBtn.querySelector(".btn-icon").setAttribute("data-lucide", "play");
        lucide.createIcons();
        fetchPapers(); // Final load refresh
    }

    // Fetch and populate papers
    async function fetchPapers() {
        try {
            const response = await fetch("/api/papers");
            const data = await response.json();
            loadedPapers = data || [];
            
            // Sort by download time / latest first
            loadedPapers.sort((a, b) => {
                return new Date(b.download_time || 0) - new Date(a.download_time || 0);
            });
            
            renderPapers(loadedPapers);
        } catch (error) {
            console.error("Failed to load papers library:", error);
        }
    }

    function renderPapers(papers) {
        statTotal.textContent = papers.length;

        if (papers.length === 0) {
            libraryList.innerHTML = `
                <div class="empty-library">
                    <i data-lucide="inbox" class="empty-icon"></i>
                    <p>No papers downloaded yet. Enter a keyword and start the agent!</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        libraryList.innerHTML = "";
        
        papers.forEach(paper => {
            const card = document.createElement("div");
            card.className = "paper-card";
            
            const pdfUrl = `/api/download_pdf/${paper.pdf_filename}`;
            const authorsText = paper.authors && paper.authors !== "N/A" ? paper.authors : "Unknown Authors";
            const journalText = paper.journal && paper.journal !== "N/A" ? paper.journal : "Unknown Journal";

            card.innerHTML = `
                <div class="paper-details">
                    <h3 class="paper-title" title="${paper.title}">${paper.title}</h3>
                    <p class="paper-authors" title="${authorsText}">${authorsText}</p>
                    <p class="paper-authors" style="font-style: italic; opacity: 0.8;" title="${journalText}">${journalText}</p>
                    <div class="paper-badges">
                        <span class="badge badge-year">${paper.year}</span>
                        <span class="badge badge-pmcid">${paper.pmcid}</span>
                        ${paper.search_keyword ? `<span class="badge badge-keyword">#${paper.search_keyword}</span>` : ""}
                    </div>
                </div>
                <div class="paper-actions">
                    <a href="${pdfUrl}" target="_blank" class="paper-btn btn-primary">
                        <i data-lucide="external-link"></i> Open PDF
                    </a>
                </div>
            `;
            libraryList.appendChild(card);
        });

        lucide.createIcons();
    }

    // Client-side instant filtering
    libraryFilter.addEventListener("input", () => {
        const query = libraryFilter.value.toLowerCase().trim();
        if (!query) {
            renderPapers(loadedPapers);
            return;
        }

        const filtered = loadedPapers.filter(paper => {
            return (
                (paper.title || "").toLowerCase().includes(query) ||
                (paper.authors || "").toLowerCase().includes(query) ||
                (paper.pmcid || "").toLowerCase().includes(query) ||
                (paper.search_keyword || "").toLowerCase().includes(query) ||
                (paper.journal || "").toLowerCase().includes(query)
            );
        });

        renderPapers(filtered);
    });
});
