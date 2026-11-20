
/* =====================================================
   EXPENSEFLOW - AUTHENTICATION, DASHBOARD & FEATURES
===================================================== */

"use strict";

/* -------------------- DOM ELEMENTS -------------------- */

const $ = (selector) => document.querySelector(selector);
const byId = (id) => document.getElementById(id);

const authScreen = byId("authScreen");
const dashboardApp = byId("dashboardApp");
const authTitle = byId("authTitle");
const authSubtitle = byId("authSubtitle");
const authMessage = byId("authMessage");

const loginForm = byId("loginForm");
const registerForm = byId("registerForm");
const showRegisterButton = byId("showRegister");
const showLoginButton = byId("showLogin");
const profileMenuButton = byId("profileMenuButton");
const profileDropdown = byId("profileDropdown");
const logoutButton = byId("logoutButton");
const topbarAvatarInitials = byId("topbarAvatarInitials");
const topbarProfileImage = byId("topbarProfileImage");
const profilePictureInput = byId("profilePictureInput");
const profilePictureMessage = byId("profilePictureMessage");

const chatbotButton = byId("chatbot-button");
const chatbotWindow = byId("chatbot-window");
const chatbotInput = byId("chatbot-input");
const chatbotMessages = byId("chatbot-messages");

const expenseForm = byId("expenseForm");
const amountInput = byId("amount");
const categoryInput = byId("category");
const dateInput = byId("expenseDate");
const descriptionInput = byId("description");
const expenseTableBody = byId("expenseTableBody");

const totalExpense = byId("totalExpense");
const monthlyExpense = byId("monthlyExpense");
const expenseCount = byId("expenseCount");
const submitExpenseBtn = byId("submitExpenseBtn");

const predictButton = byId("predictButton");
const predictionResult = byId("predictionResult");
const predictionDetails = byId("predictionDetails");
const predictedAmount = byId("predictedAmount");
const averageAmount = byId("averageAmount");
const percentageDifference = byId("percentageDifference");
const predictionTrend = byId("predictionTrend");

let currentUser = null;
let editingExpenseId = null;
let categoryChart = null;
let monthlyChart = null;
let expenseRequestInProgress = false;

/* -------------------- GENERAL HELPERS -------------------- */

function formatRupees(value) {
    const amount = Number(value);

    if (!Number.isFinite(amount)) {
        return "₹0.00";
    }

    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

function setText(element, value) {
    if (element) {
        element.textContent = value;
    }
}

function setHidden(element, hidden) {
    if (element) {
        element.hidden = hidden;
    }
}

/*
 * Parse API responses safely. This also provides a useful
 * error if Flask returns an HTML error page instead of JSON.
 */
async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: {
            ...(options.body ? {
                "Content-Type": "application/json"
            } : {}),
            ...(options.headers || {})
        }
    });

    const text = await response.text();
    let data = {};

    if (text.trim()) {
        try {
            data = JSON.parse(text);
        } catch {
            if (response.ok) {
                throw new Error(
                    "The server returned an unexpected response."
                );
            }
        }
    }

    if (!response.ok) {
        const message =
            data.error ||
            data.message ||
            (response.status === 401
                ? "Your session has expired. Please log in again."
                : `Request failed (${response.status}).`);

        const error = new Error(message);
        error.status = response.status;
        throw error;
    }

    return data;
}

function isUnauthenticated(error) {
    return error && error.status === 401;
}

function getInitials(name) {
    return String(name || "User")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map(part => part.charAt(0).toUpperCase())
        .join("");
}

/* -------------------- PROFILE PICTURE DISPLAY -------------------- */

function displayProfilePicture(pictureUrl, initials) {
    if (!topbarAvatarInitials || !topbarProfileImage) {
        return;
    }

    // Always prepare the initials as a fallback.
    setText(topbarAvatarInitials, initials || "👤");
    setHidden(topbarAvatarInitials, false);
    setHidden(topbarProfileImage, true);

    topbarProfileImage.onerror = function () {
        topbarProfileImage.removeAttribute("src");
        setHidden(topbarProfileImage, true);
        setHidden(topbarAvatarInitials, false);
    };

    if (typeof pictureUrl !== "string" || !pictureUrl.trim()) {
        topbarProfileImage.removeAttribute("src");
        return;
    }

    topbarProfileImage.src = pictureUrl;
    setHidden(topbarProfileImage, false);
    setHidden(topbarAvatarInitials, true);
}

/* -------------------- AUTHENTICATION -------------------- */

function showAuth(mode = "login", message = "", messageType = "error") {
    currentUser = null;

    setHidden(authScreen, false);
    setHidden(dashboardApp, true);
    setHidden(chatbotButton, true);
    setHidden(chatbotWindow, true);

    setHidden(loginForm, mode !== "login");
    setHidden(registerForm, mode !== "register");

    setText(
        authTitle,
        mode === "login" ? "Welcome back!" : "Create your account"
    );

    setText(
        authSubtitle,
        mode === "login"
            ? "Log in to manage your expenses securely."
            : "Start managing your finances with ExpenseFlow."
    );

    setText(authMessage, message);
    setHidden(authMessage, !message);

    if (authMessage) {
        authMessage.classList.remove("success", "error");
        if (message) {
            authMessage.classList.add(messageType);
        }
    }
}


function showDashboard(user) {
    if (!user || !user.name) {
        showAuth("login", "The server did not return valid user details.");
        return;
    }

    currentUser = user;

    setHidden(authScreen, true);
    setHidden(dashboardApp, false);
    setHidden(chatbotButton, false);
    setHidden(chatbotWindow, true);

    const welcomeHeading = $(".welcome-section h1");
    const profileName = $(".profile-info strong");
    const profileAvatar = $(".profile-avatar");

    setText(welcomeHeading, `Welcome back, ${user.name}`);
    setText(profileName, user.name);

    const initials = getInitials(user.name);

    // Preserve the existing dashboard profile initials.
    setText(profileAvatar, initials);

    // Show this user's saved picture, or their initials if absent.
    displayProfilePicture(user.profile_picture, initials);

    // Close the dropdown when changing accounts or logging in.
    if (profileDropdown) {
        profileDropdown.hidden = true;
    }

    profileMenuButton?.setAttribute("aria-expanded", "false");

    // Refresh the dashboard after login.
    loadExpenses();
}


async function submitAuthForm(endpoint, payload, form) {
    if (!form) return;

    const submitButton = form.querySelector('button[type="submit"]');

    setText(authMessage, "Please wait...");
    setHidden(authMessage, false);

    if (authMessage) {
        authMessage.classList.remove("success", "error");
    }

    if (submitButton) {
        submitButton.disabled = true;
    }

    try {
        const data = await apiRequest(endpoint, {
            method: "POST",
            body: JSON.stringify(payload)
        });

        if (!data.user) {
            throw new Error(
                "Authentication succeeded, but user details were not returned."
            );
        }

        form.reset();
        showDashboard(data.user);
    } catch (error) {
        setText(authMessage, error.message);
        setHidden(authMessage, false);

        if (authMessage) {
            authMessage.classList.remove("success");
            authMessage.classList.add("error");
        }

        console.error("Authentication error:", error);
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
        }
    }
}

if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        await submitAuthForm(
            "/api/login",
            {
                email: byId("loginEmail")?.value.trim() || "",
                password: byId("loginPassword")?.value || ""
            },
            loginForm
        );
    });
}

if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        await submitAuthForm(
            "/api/register",
            {
                name: byId("registerName")?.value.trim() || "",
                email: byId("registerEmail")?.value.trim() || "",
                password: byId("registerPassword")?.value || ""
            },
            registerForm
        );
    });
}

if (showRegisterButton) {
    showRegisterButton.addEventListener("click", () => {
        registerForm?.reset();
        showAuth("register");
    });
}

if (showLoginButton) {
    showLoginButton.addEventListener("click", () => {
        loginForm?.reset();
        showAuth("login");
    });
}

async function logout() {
    try {
        await apiRequest("/api/logout", {
            method: "POST"
        });

        editingExpenseId = null;
        expenseRequestInProgress = false;

        if (expenseForm) {
            expenseForm.reset();
        }

        setText(submitExpenseBtn, "＋ Add Expense");
        setText(expenseTableBody, "");

        destroyCharts();
        resetPrediction();
        resetChatbot();

        loginForm?.reset();
        registerForm?.reset();

        showAuth(
            "login",
            "You have logged out successfully.",
            "success"
        );
    } catch (error) {
        console.error("Logout error:", error);
        alert(error.message || "Unable to log out.");
    }
}


/* -------------------- PROFILE MENU -------------------- */

// Open and close the profile dropdown.
if (profileMenuButton && profileDropdown) {
    profileMenuButton.addEventListener("click", function (event) {
        event.stopPropagation();

        const isOpening = profileDropdown.hidden;
        profileDropdown.hidden = !isOpening;

        profileMenuButton.setAttribute(
            "aria-expanded",
            String(isOpening)
        );
    });

    // Close the menu when clicking elsewhere.
    document.addEventListener("click", function (event) {
        if (!event.target.closest(".profile-dropdown-container")) {
            profileDropdown.hidden = true;
            profileMenuButton.setAttribute("aria-expanded", "false");
        }
    });

    // Close the menu when pressing Escape.
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            profileDropdown.hidden = true;
            profileMenuButton.setAttribute("aria-expanded", "false");
        }
    });
}

// Connect the dropdown Logout option to your existing logout function.
if (logoutButton) {
    logoutButton.addEventListener("click", function () {
        if (profileDropdown) {
            profileDropdown.hidden = true;
        }

        profileMenuButton?.setAttribute("aria-expanded", "false");

        logout();
    });
}


/* -------------------- PROFILE PICTURE UPLOAD -------------------- */

if (profilePictureInput) {
    profilePictureInput.addEventListener("change", async function () {
        const file = profilePictureInput.files?.[0];

        if (!file) return;

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];

        if (!allowedTypes.includes(file.type)) {
            setText(
                profilePictureMessage,
                "Please choose a JPG, PNG, or WEBP image."
            );
            setHidden(profilePictureMessage, false);
            profilePictureInput.value = "";
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            setText(
                profilePictureMessage,
                "Image size must be 5 MB or less."
            );
            setHidden(profilePictureMessage, false);
            profilePictureInput.value = "";
            return;
        }

        const formData = new FormData();
        formData.append("profile_picture", file);

        setText(profilePictureMessage, "Uploading picture...");
        setHidden(profilePictureMessage, false);

        try {
            // Do not set Content-Type manually for FormData.
            // The browser must add the multipart boundary.
            const response = await fetch("/api/profile-picture", {
                method: "POST",
                credentials: "same-origin",
                body: formData
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const error = new Error(
                    data.error || `Upload failed (${response.status}).`
                );
                error.status = response.status;
                throw error;
            }

            if (!data.profile_picture) {
                throw new Error("The server did not return the picture URL.");
            }

            // Update the current user's details in memory.
            if (currentUser) {
                currentUser.profile_picture = data.profile_picture;
            }

            // Show the uploaded picture immediately.
            displayProfilePicture(
                data.profile_picture,
                getInitials(currentUser?.name)
            );

            setText(
                profilePictureMessage,
                "Profile picture updated successfully!"
            );
            setHidden(profilePictureMessage, false);
        } catch (error) {
            console.error("Profile picture upload error:", error);

            setText(
                profilePictureMessage,
                error.message || "Unable to upload the picture."
            );
            setHidden(profilePictureMessage, false);

            if (isUnauthenticated(error)) {
                showAuth("login", "Please log in again to continue.");
            }
        } finally {
            // Allow selecting the same file again if needed.
            profilePictureInput.value = "";
        }
    });
}

async function checkSession() {
    try {
        const data = await apiRequest("/api/me");

        if (data.authenticated && data.user) {
            showDashboard(data.user);
        } else {
            showAuth("login");
        }
    } catch (error) {
        if (isUnauthenticated(error)) {
            showAuth("login");
        } else {
            console.error("Session check failed:", error);
            showAuth(
                "login",
                "Unable to connect. Please check that the server is running."
            );
        }
    }
}

/* -------------------- EXPENSE FORM -------------------- */

if (expenseForm) {
    expenseForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (expenseRequestInProgress) return;

        const amount = Number(amountInput?.value);

        if (!Number.isFinite(amount) || amount <= 0) {
            alert("Please enter an amount greater than zero.");
            return;
        }

        if (!categoryInput?.value || !dateInput?.value) {
            alert("Please select an expense category and date.");
            return;
        }

        const expense = {
            amount,
            category: categoryInput.value,
            date: dateInput.value,
            description: descriptionInput?.value.trim() || ""
        };

        const expenseId = editingExpenseId;
        const url = expenseId !== null
            ? `/api/expenses/${encodeURIComponent(expenseId)}`
            : "/api/expenses";

        const method = expenseId !== null ? "PUT" : "POST";

        expenseRequestInProgress = true;

        if (submitExpenseBtn) {
            submitExpenseBtn.disabled = true;
        }

        try {
            await apiRequest(url, {
                method,
                body: JSON.stringify(expense)
            });

            expenseForm.reset();
            editingExpenseId = null;
            setText(submitExpenseBtn, "＋ Add Expense");

            await loadExpenses();
        } catch (error) {
            console.error("Save expense error:", error);

            if (isUnauthenticated(error)) {
                showAuth("login", "Please log in again to continue.");
            } else {
                alert(error.message || "Unable to save the expense.");
            }
        } finally {
            expenseRequestInProgress = false;

            if (submitExpenseBtn) {
                submitExpenseBtn.disabled = false;
            }
        }
    });
}

/* -------------------- LOAD EXPENSES -------------------- */

async function loadExpenses() {
    try {
        const expenses = await apiRequest("/api/expenses");

        if (!Array.isArray(expenses)) {
            throw new Error("The server returned an invalid expense list.");
        }

        displayExpenses(expenses);
        updateDashboard(expenses);

        loadCategoryChart(expenses);
        loadMonthlyChart(expenses);
        loadSpendingInsights(expenses);

        // Refresh monthly budget after expense changes.
        await loadMonthlyBudget();

        // Refresh historical budget records after expense changes.
        await loadBudgetHistory();
    } catch (error) {
        console.error("Unable to refresh dashboard:", error);

        if (isUnauthenticated(error)) {
            showAuth("login", "Your session has expired. Please log in again.");
        }
    }
}

/* -------------------- DISPLAY EXPENSES -------------------- */

function displayExpenses(expenses) {
    if (!expenseTableBody) return;

    expenseTableBody.replaceChildren();

    if (expenses.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.textContent = "No expenses yet. Add your first expense above.";
        cell.style.textAlign = "center";
        cell.style.padding = "24px";

        row.appendChild(cell);
        expenseTableBody.appendChild(row);
        return;
    }

    expenses.forEach((expense) => {
        const row = document.createElement("tr");

        const dateCell = document.createElement("td");
        dateCell.textContent = expense.date || "—";

        const categoryCell = document.createElement("td");
        categoryCell.textContent = expense.category || "Uncategorized";

        const descriptionCell = document.createElement("td");
        descriptionCell.textContent = expense.description || "—";

        const amountCell = document.createElement("td");
        amountCell.textContent = formatRupees(expense.amount);

        const actionsCell = document.createElement("td");

        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "edit-btn";
        editButton.textContent = "Edit";
        editButton.addEventListener("click", () => {
            editExpense(expense.id);
        });

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "delete-btn";
        deleteButton.textContent = "Delete";
        deleteButton.addEventListener("click", () => {
            deleteExpense(expense.id);
        });

        actionsCell.append(editButton, deleteButton);
        row.append(
            dateCell,
            categoryCell,
            descriptionCell,
            amountCell,
            actionsCell
        );

        expenseTableBody.appendChild(row);
    });
}

/* -------------------- EDIT EXPENSE -------------------- */

async function editExpense(expenseId) {
    try {
        const expenses = await apiRequest("/api/expenses");

        const expense = expenses.find(
            item => String(item.id) === String(expenseId)
        );

        if (!expense) {
            alert("Expense not found. Refresh the dashboard and try again.");
            return;
        }

        editingExpenseId = expenseId;

        if (amountInput) amountInput.value = expense.amount;
        if (categoryInput) categoryInput.value = expense.category;
        if (dateInput) dateInput.value = String(expense.date).slice(0, 10);
        if (descriptionInput) {
            descriptionInput.value = expense.description || "";
        }

        setText(submitExpenseBtn, "Update Expense");

        showView("add-expense");

        amountInput?.focus();
    } catch (error) {
        console.error("Edit expense error:", error);
        alert(error.message || "Unable to load the selected expense.");
    }
}

/* -------------------- DELETE EXPENSE -------------------- */

async function deleteExpense(expenseId) {
    if (!confirm("Are you sure you want to delete this expense?")) {
        return;
    }

    try {
        await apiRequest(
            `/api/expenses/${encodeURIComponent(expenseId)}`,
            { method: "DELETE" }
        );

        if (String(editingExpenseId) === String(expenseId)) {
            editingExpenseId = null;
            expenseForm?.reset();
            setText(submitExpenseBtn, "＋ Add Expense");
        }

        await loadExpenses();
    } catch (error) {
        console.error("Delete expense error:", error);
        alert(error.message || "Unable to delete the expense.");
    }
}

/* -------------------- DASHBOARD SUMMARY -------------------- */

function updateDashboard(expenses) {
    let total = 0;
    let monthlyTotal = 0;

    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    expenses.forEach((expense) => {
        const amount = Number(expense.amount);

        if (!Number.isFinite(amount)) return;

        total += amount;

        if (!expense.date) return;

        // Parse YYYY-MM-DD as a local calendar date.
        const parts = String(expense.date).slice(0, 10).split("-");
        if (parts.length !== 3) return;

        const year = Number(parts[0]);
        const month = Number(parts[1]);
        const day = Number(parts[2]);

        if (
            Number.isInteger(year) &&
            Number.isInteger(month) &&
            Number.isInteger(day) &&
            month >= 1 && month <= 12 &&
            day >= 1 && day <= 31 &&
            month - 1 === currentMonth &&
            year === currentYear
        ) {
            monthlyTotal += amount;
        }
    });

    setText(totalExpense, formatRupees(total));
    setText(monthlyExpense, formatRupees(monthlyTotal));
    setText(expenseCount, String(expenses.length));
}

/* -------------------- CHART CLEANUP -------------------- */

function destroyCharts() {
    if (categoryChart) {
        categoryChart.destroy();
        categoryChart = null;
    }

    if (monthlyChart) {
        monthlyChart.destroy();
        monthlyChart = null;
    }
}

/* -------------------- CATEGORY CHART -------------------- */

function loadCategoryChart(expenses) {
    const canvas = byId("categoryChart");

    if (!canvas || typeof Chart === "undefined") {
        console.warn("Category chart canvas or Chart.js is unavailable.");
        return;
    }

    const totals = {};

    expenses.forEach((expense) => {
        const amount = Number(expense.amount);
        if (!Number.isFinite(amount)) return;

        const category = expense.category || "Uncategorized";
        totals[category] = (totals[category] || 0) + amount;
    });

    if (categoryChart) {
        categoryChart.destroy();
        categoryChart = null;
    }

    categoryChart = new Chart(canvas, {
        type: "pie",
        data: {
            labels: Object.keys(totals),
            datasets: [{
                label: "Expenses by Category",
                data: Object.values(totals),
                backgroundColor: [
                    "#635bff",
                    "#12b76a",
                    "#2e90fa",
                    "#f79009",
                    "#f04438",
                    "#9b8afb",
                    "#36bffa",
                    "#ee46bc"
                ],
                borderWidth: 2,
                borderColor: "#ffffff"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom"
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            return `${context.label}: ${formatRupees(context.raw)}`;
                        }
                    }
                }
            }
        }
    });
}

/* -------------------- MONTHLY CHART -------------------- */

function loadMonthlyChart(expenses) {
    const canvas = byId("monthlyChart");

    if (!canvas || typeof Chart === "undefined") {
        console.warn("Monthly chart canvas or Chart.js is unavailable.");
        return;
    }

    const totals = {};

    expenses.forEach((expense) => {
        if (!expense.date) return;

        const month = String(expense.date).slice(0, 7);
        const amount = Number(expense.amount);

        if (!/^\d{4}-\d{2}$/.test(month) || !Number.isFinite(amount)) {
            return;
        }

        totals[month] = (totals[month] || 0) + amount;
    });

    const months = Object.keys(totals).sort();

    const labels = months.map((month) => {
        const [year, monthNumber] = month.split("-").map(Number);
        return new Date(year, monthNumber - 1, 1).toLocaleDateString(
            "en-IN",
            { month: "short", year: "numeric" }
        );
    });

    if (monthlyChart) {
        monthlyChart.destroy();
        monthlyChart = null;
    }

    monthlyChart = new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Monthly Expenses",
                data: months.map(month => totals[month]),
                backgroundColor: "#8178ff",
                hoverBackgroundColor: "#5146e5",
                borderRadius: 6,
                maxBarThickness: 55
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            return formatRupees(context.raw);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback(value) {
                            return "₹" + Number(value).toLocaleString("en-IN");
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/* -------------------- SPENDING INSIGHTS -------------------- */

function loadSpendingInsights(expenses) {
    const averageElement = byId("averageExpense");
    const topCategoryElement = byId("topCategory");
    const highestElement = byId("highestExpense");

    const validExpenses = expenses.filter((expense) =>
        Number.isFinite(Number(expense.amount))
    );

    if (validExpenses.length === 0) {
        setText(averageElement, formatRupees(0));
        setText(topCategoryElement, "—");
        setText(highestElement, formatRupees(0));
        return;
    }

    const amounts = validExpenses.map(expense => Number(expense.amount));
    const total = amounts.reduce((sum, amount) => sum + amount, 0);
    const highest = Math.max(...amounts);

    setText(
        averageElement,
        formatRupees(total / validExpenses.length)
    );
    setText(highestElement, formatRupees(highest));

    const categoryTotals = {};

    validExpenses.forEach((expense) => {
        const category = expense.category || "Uncategorized";
        categoryTotals[category] =
            (categoryTotals[category] || 0) + Number(expense.amount);
    });

    const topCategory = Object.keys(categoryTotals).sort(
        (a, b) => categoryTotals[b] - categoryTotals[a]
    )[0];

    setText(topCategoryElement, topCategory || "—");
}

/* -------------------- EXPENSE PREDICTION -------------------- */

function resetPrediction() {
    setText(predictionResult, "Use the button to predict your next month's expenses.");
    setHidden(predictionDetails, true);

    setText(predictedAmount, "—");
    setText(averageAmount, "—");
    setText(percentageDifference, "—");
    setText(predictionTrend, "—");
}

if (predictButton) {
    predictButton.addEventListener("click", async () => {
        predictButton.disabled = true;
        setHidden(predictionDetails, true);
        setText(predictionResult, "Calculating your expense prediction...");

        try {
            const result = await apiRequest("/api/ml/predict");
            const predicted = Number(result.predicted_expense);

            if (!Number.isFinite(predicted)) {
                throw new Error(
                    "The server did not return a valid predicted expense."
                );
            }

            setText(predictedAmount, formatRupees(predicted));

            /*
             * Some backend versions return only predicted_expense.
             * Treat the other metrics as optional so a valid prediction
             * is not rejected when those fields are absent.
             */
            const average = Number(result.average_monthly_expense);
            const difference = Number(result.percentage_difference);

            setText(
                averageAmount,
                Number.isFinite(average) && result.average_monthly_expense != null
                    ? formatRupees(average)
                    : "Not available"
            );

            setText(
                percentageDifference,
                Number.isFinite(difference) && result.percentage_difference != null
                    ? `${difference > 0 ? "+" : ""}${difference.toFixed(2)}%`
                    : "Not available"
            );

            let trend = result.trend;

            if (typeof trend !== "string" || !trend.trim()) {
                trend = Number.isFinite(difference)
                    ? difference > 0
                        ? "Spending may increase"
                        : difference < 0
                            ? "Spending may decrease"
                            : "Spending may remain stable"
                    : "Based on available expense data";
            }

            setText(predictionTrend, trend);

            setText(
                predictionResult,
                `Your predicted expense for next month is ${formatRupees(predicted)}.`
            );

            setHidden(predictionDetails, false);
        } catch (error) {
            console.error("Prediction error:", error);

            setText(
                predictionResult,
                error.message || "Unable to calculate the prediction. Please try again."
            );

            if (isUnauthenticated(error)) {
                showAuth("login", "Please log in again to continue.");
            }
        } finally {
            predictButton.disabled = false;
        }
    });
}

/* -------------------- CHATBOT -------------------- */

function toggleChatbot() {
    if (!chatbotWindow || !currentUser) return;

    chatbotWindow.hidden = !chatbotWindow.hidden;

    if (!chatbotWindow.hidden) {
        chatbotInput?.focus();

        if (chatbotMessages) {
            chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        }
    }
}

function handleChatKey(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function addChatMessage(message, className) {
    if (!chatbotMessages) return;

    const element = document.createElement("div");
    element.className = className;
    element.textContent = message;

    chatbotMessages.appendChild(element);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function resetChatbot() {
    if (!chatbotMessages) return;

    chatbotMessages.replaceChildren();

    addChatMessage(
        "Hi! 👋 I can help you understand your expenses.",
        "bot-message"
    );

    if (chatbotInput) {
        chatbotInput.value = "";
    }
}

async function sendMessage() {
    if (!chatbotInput || !chatbotMessages || !currentUser) return;

    const message = chatbotInput.value.trim();

    if (!message) return;

    addChatMessage(message, "user-message");
    chatbotInput.value = "";

    const sendButton = $("#chatbot-input-area button");

    if (sendButton) {
        sendButton.disabled = true;
    }

    try {
        const data = await apiRequest("/api/chatbot", {
            method: "POST",
            body: JSON.stringify({ message })
        });

        if (!data.response) {
            throw new Error("The chatbot returned an empty response.");
        }

        addChatMessage(String(data.response), "bot-message");
    } catch (error) {
        console.error("Chatbot error:", error);

        addChatMessage(
            error.message || "Sorry, something went wrong. Please try again.",
            "bot-message"
        );

        if (isUnauthenticated(error)) {
            showAuth("login", "Please log in again to continue.");
        }
    } finally {
        if (sendButton) {
            sendButton.disabled = false;
        }

        chatbotInput.focus();
    }
}

/* -------------------- STARTUP -------------------- */

// Start with both main screens hidden until session status is checked.
setHidden(authScreen, true);
setHidden(dashboardApp, true);
setHidden(chatbotButton, true);
setHidden(chatbotWindow, true);

resetPrediction();
resetChatbot();
checkSession();

// =====================================
// MONTHLY BUDGET MANAGEMENT
// =====================================

const budgetMonthInput = document.getElementById("budgetMonth");
const budgetAmountInput = document.getElementById("budgetAmount");
const saveBudgetButton = document.getElementById("saveBudgetButton");

const budgetMessage = document.getElementById("budgetMessage");
const budgetTotal = document.getElementById("budgetTotal");
const budgetSpent = document.getElementById("budgetSpent");
const budgetRemaining = document.getElementById("budgetRemaining");
const budgetPercentage = document.getElementById("budgetPercentage");

const budgetProgressBar = document.getElementById("budgetProgressBar");
const budgetProgressTrack = document.getElementById("budgetProgressTrack");
const budgetAlert = document.getElementById("budgetAlert");

function getCurrentBudgetMonth() {
    const now = new Date();

    return `${now.getFullYear()}-${String(
        now.getMonth() + 1
    ).padStart(2, "0")}`;
}

function formatBudgetCurrency(amount) {
    return Number(amount).toLocaleString("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2
    });
}

// Load budget details from Flask
async function loadMonthlyBudget() {
    const month = budgetMonthInput.value;

    if (!month) return;

    try {
        const response = await fetch(
            `/api/budgets?month=${encodeURIComponent(month)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to load budget.");
        }

        budgetTotal.textContent = formatBudgetCurrency(data.budget);
        budgetSpent.textContent = formatBudgetCurrency(data.total_spent);
        budgetRemaining.textContent = formatBudgetCurrency(data.remaining);

        const percentage = Number(data.percentage_used) || 0;

        budgetPercentage.textContent = `${percentage.toFixed(1)}%`;

        // Keep the visual progress bar within 0–100%.
        const progress = Math.min(Math.max(percentage, 0), 100);

        budgetProgressBar.style.width = `${progress}%`;

        // Change progress colour according to budget usage.
        if (percentage >= 100) {
            budgetProgressBar.style.background = "#f04438";
        } else if (percentage >= 80) {
            budgetProgressBar.style.background = "#f79009";
        } else {
            budgetProgressBar.style.background =
                "#7a4dff";
        }

        budgetProgressTrack.setAttribute(
            "aria-valuenow",
            progress.toFixed(0)
        );

        // Budget alerts
        if (!data.has_budget) {
            budgetAlert.textContent =
                "Set a budget to start tracking your spending.";
            budgetAlert.className = "";
            budgetAmountInput.value = "";
        } else {
            budgetAmountInput.value = data.budget;

            if (percentage >= 100) {
                budgetAlert.textContent =
                    "⚠️ Budget exceeded! You have spent more than your limit.";
                budgetAlert.className = "budget-danger";
            } else if (percentage >= 80) {
                budgetAlert.textContent =
                    "⚠️ Warning! You have used 80% or more of your budget.";
                budgetAlert.className = "budget-warning";
            } else {
                budgetAlert.textContent =
                    "✓ You are within your monthly budget. Keep it up!";
                budgetAlert.className = "budget-success";
            }
        }

    } catch (error) {
        console.error("Budget loading error:", error);
        budgetAlert.textContent = error.message;
    }
}

// Save or update monthly budget
async function saveMonthlyBudget() {
    const month = budgetMonthInput.value;
    const amount = Number(budgetAmountInput.value);

    if (!month) {
        budgetMessage.textContent = "Please select a month.";
        return;
    }

    if (!Number.isFinite(amount) || amount <= 0) {
        budgetMessage.textContent =
            "Please enter a valid budget amount greater than zero.";
        return;
    }

    saveBudgetButton.disabled = true;
    saveBudgetButton.textContent = "Saving...";

    try {
        const response = await fetch("/api/budgets", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                month: month,
                amount: amount
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to save budget.");
        }

        budgetMessage.textContent =
            "✓ Monthly budget saved successfully.";

        await loadMonthlyBudget();
        await loadBudgetHistory();

    } catch (error) {
        console.error("Budget saving error:", error);
        budgetMessage.textContent = error.message;

    } finally {
        saveBudgetButton.disabled = false;
        saveBudgetButton.textContent = "Save Budget";
    }
}

// Event listeners
saveBudgetButton.addEventListener("click", saveMonthlyBudget);

budgetMonthInput.addEventListener("change", loadMonthlyBudget);

// Initialize budget section
budgetMonthInput.value = getCurrentBudgetMonth();
loadMonthlyBudget();


/* =====================================
   MONTHLY BUDGET HISTORY
===================================== */

const budgetHistoryTableBody = byId("budgetHistoryTableBody");
const budgetHistoryMessage = byId("budgetHistoryMessage");
const budgetHistoryWrapper = byId("budgetHistoryWrapper");
const refreshBudgetHistoryButton = byId("refreshBudgetHistory");

// Convert YYYY-MM into a readable month name.
function formatHistoryMonth(month) {
    const [year, monthNumber] = month.split("-").map(Number);

    return new Date(year, monthNumber - 1, 1).toLocaleDateString(
        "en-IN",
        {
            month: "long",
            year: "numeric"
        }
    );
}

// Load historical budgets from Flask.
async function loadBudgetHistory() {

    if (!budgetHistoryTableBody) return;

    budgetHistoryMessage.textContent = "Loading budget history...";
    budgetHistoryWrapper.hidden = true;

    try {
        const data = await apiRequest("/api/budgets/history");

        const history = data.history;

        budgetHistoryTableBody.replaceChildren();

        if (!Array.isArray(history) || history.length === 0) {
            budgetHistoryMessage.textContent =
                "No budget history available yet. Save your first monthly budget to get started.";

            return;
        }

        history.forEach((item) => {

            const row = document.createElement("tr");

            // Month
            const monthCell = document.createElement("td");
            monthCell.textContent = formatHistoryMonth(item.month);

            // Budget
            const budgetCell = document.createElement("td");
            budgetCell.textContent =
                formatBudgetCurrency(item.budget);

            // Total spent
            const spentCell = document.createElement("td");
            spentCell.textContent =
                formatBudgetCurrency(item.total_spent);

            // Remaining balance
            const remainingCell = document.createElement("td");
            remainingCell.textContent =
                formatBudgetCurrency(item.remaining);

            // Percentage used
            const percentageCell = document.createElement("td");
            percentageCell.textContent =
                `${Number(item.percentage_used).toFixed(1)}%`;

            // Budget status
            const statusCell = document.createElement("td");
            const statusBadge = document.createElement("span");

            statusBadge.textContent = item.status;
            statusBadge.className =
                "budget-history-status " +
                String(item.status).toLowerCase().replace(/\s+/g, "-");

            statusCell.appendChild(statusBadge);

            row.append(
                monthCell,
                budgetCell,
                spentCell,
                remainingCell,
                percentageCell,
                statusCell
            );

            budgetHistoryTableBody.appendChild(row);
        });

        budgetHistoryMessage.textContent =
            `Showing ${data.total_months} month(s) of budget history.`;

        budgetHistoryWrapper.hidden = false;

    } catch (error) {

        console.error("Budget history loading error:", error);

        budgetHistoryMessage.textContent =
            error.message || "Unable to load budget history.";

        if (isUnauthenticated(error)) {
            showAuth("login", "Please log in again to continue.");
        }
    }
}

// Manually refresh history.
if (refreshBudgetHistoryButton) {
    refreshBudgetHistoryButton.addEventListener(
        "click",
        loadBudgetHistory
    );
}

// Initial history loading after the budget section initializes.
loadBudgetHistory();


/* ==========================================
   FORGOT PASSWORD AND OTP RESET FLOW
========================================== */

(function () {
    let passwordResetEmail = "";

    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const forgotForm = document.getElementById("forgotPasswordForm");
    const verifyOTPForm = document.getElementById("verifyResetOTPForm");
    const resetPasswordForm = document.getElementById("resetPasswordForm");

    const authTitle = document.getElementById("authTitle");
    const authSubtitle = document.getElementById("authSubtitle");
    const authMessage = document.getElementById("authMessage");

    function showResetMessage(message) {
        authMessage.textContent = message;
    }

    function showResetScreen(screen) {
        loginForm.hidden = screen !== "login";
        registerForm.hidden = screen !== "register";
        forgotForm.hidden = screen !== "forgot";
        verifyOTPForm.hidden = screen !== "otp";
        resetPasswordForm.hidden = screen !== "reset";

        const screenDetails = {
            login: [
                "Welcome back!",
                "Log in to manage your expenses securely."
            ],
            forgot: [
                "Forgot Password?",
                "Enter your registered email to receive a verification code."
            ],
            otp: [
                "Verify Your Email",
                "Enter the six-digit code sent to your email address."
            ],
            reset: [
                "Create New Password",
                "Choose a strong password for your account."
            ]
        };

        if (screenDetails[screen]) {
            authTitle.textContent = screenDetails[screen][0];
            authSubtitle.textContent = screenDetails[screen][1];
        }

        authMessage.textContent = "";
    }

    async function passwordResetRequest(endpoint, payload) {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "same-origin",
            body: JSON.stringify(payload)
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(
                data.error || data.message || "Something went wrong. Please try again."
            );
        }

        return data;
    }

    // 1. Open Forgot Password screen
    document.getElementById("forgotPasswordLink")
        .addEventListener("click", function (event) {
            event.preventDefault();

            const loginEmail = document.getElementById("loginEmail").value.trim();

            document.getElementById("forgotEmail").value = loginEmail;

            showResetScreen("forgot");
        });

    // 2. Send OTP to registered email
    forgotForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        passwordResetEmail = document.getElementById("forgotEmail").value.trim();

        const button = forgotForm.querySelector('button[type="submit"]');
        button.disabled = true;

        try {
            await passwordResetRequest("/api/forgot-password", {
                email: passwordResetEmail
            });

            document.getElementById("resetOTPEmail").value = passwordResetEmail;

            showResetScreen("otp");
            showResetMessage(
                "If an account exists for this email, a verification code has been sent."
            );

        } catch (error) {
            showResetMessage(error.message);
        } finally {
            button.disabled = false;
        }
    });

    // 3. Verify OTP

    verifyOTPForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const otpInput = document.getElementById("resetOTP");
        const otpError = document.getElementById("otpError");

        const otp = otpInput.value.trim();
        const button = verifyOTPForm.querySelector('button[type="submit"]');

        otpError.textContent = "";
        otpInput.classList.remove("input-error");

        button.disabled = true;

        try {
            await passwordResetRequest("/api/verify-reset-otp", {
                email: passwordResetEmail,
                otp: otp
            });

            showResetScreen("reset");

            showResetMessage(
                "Email verified successfully. Create your new password."
            );

        } catch (error) {

            otpError.textContent = error.message;
            otpInput.classList.add("input-error");

        } finally {
            button.disabled = false;
        }
    });

    // Clear OTP error when user starts typing again
    document.getElementById("resetOTP").addEventListener("input", function () {
        document.getElementById("otpError").textContent = "";
        this.classList.remove("input-error");
    });

    // 4. Reset password
    resetPasswordForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const newPassword = document.getElementById("newPassword").value;
        const confirmPassword = document.getElementById("confirmNewPassword").value;

        const button = resetPasswordForm.querySelector('button[type="submit"]');

        if (newPassword.length < 8 ||
            !/[A-Z]/.test(newPassword) ||
            !/[a-z]/.test(newPassword) ||
            !/[0-9]/.test(newPassword) ||
            !/[^A-Za-z0-9]/.test(newPassword)) {

            showResetMessage(
                "Password must contain at least 8 characters, uppercase, lowercase, number and special character."
            );
            return;
        }

        if (newPassword !== confirmPassword) {
            showResetMessage("Passwords do not match.");
            return;
        }

        button.disabled = true;

        try {
            await passwordResetRequest("/api/reset-password", {
                email: passwordResetEmail,
                new_password: newPassword,
                confirm_password: confirmPassword
            });

            resetPasswordForm.reset();
            verifyOTPForm.reset();
            forgotForm.reset();

            document.getElementById("loginEmail").value = passwordResetEmail;
            document.getElementById("loginPassword").value = "";

            showResetScreen("login");
            showResetMessage(
                "Password reset successfully! Please log in with your new password."
            );

            passwordResetEmail = "";

        } catch (error) {
            showResetMessage(error.message);
        } finally {
            button.disabled = false;
        }
    });

    // 5. Back to Login buttons
    document.getElementById("backToLoginFromForgot")
        .addEventListener("click", function () {
            showResetScreen("login");
        });

    document.getElementById("backToLoginFromOTP")
        .addEventListener("click", function () {
            showResetScreen("login");
        });

    document.getElementById("backToLoginFromReset")
        .addEventListener("click", function () {
            showResetScreen("login");
        });

})();


/* =====================================
   FIXED PAGES — one view per nav tab, no page scrolling
===================================== */
const VIEW_ELEMENTS = [...document.querySelectorAll(".view")];

function showView(name) {
    if (!VIEW_ELEMENTS.some(view => view.dataset.view === name)) {
        name = "overview";
    }

    VIEW_ELEMENTS.forEach(view => { view.hidden = view.dataset.view !== name; });

    document.querySelectorAll(".nav-pills .nav-link").forEach(link => {
        link.classList.toggle("active", link.dataset.view === name);
    });

    history.replaceState(null, "", "#" + name);

    // Charts drawn while hidden have no size; redraw them once visible.
    requestAnimationFrame(() => {
        if (categoryChart) categoryChart.resize();
        if (monthlyChart) monthlyChart.resize();
    });
}

document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-view]");
    if (!link) return;
    event.preventDefault();
    showView(link.dataset.view);
});

showView(location.hash.slice(1) || "overview");
