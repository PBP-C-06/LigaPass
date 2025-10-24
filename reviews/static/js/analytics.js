// ====================================
// === GENERIC FETCH HELPER ===========
// ====================================

async function fetchJSON(url, params = {}) {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${url}?${query}`);
  if (!response.ok) throw new Error("Network error");
  return response.json();
}

// ====================================
// === ADMIN ANALYTICS ================
// ====================================

function initAdminAnalytics() {
  const ticketSelect = document.getElementById("ticketPeriod"); // dropdown kiri
  const revenueSelect = document.getElementById("revenuePeriod"); // dropdown kanan

  let revenueChart = null;
  let ticketChart = null;

  // --- Update Total Tiket Terjual ---
  async function updateTicketChart() {
    const period = ticketSelect.value.toLowerCase();
    try {
      const data = await fetchJSON("/reviews/analytics/admin/data/", { period });
      const labels = data.ticketsData.map((d) => d.date);
      const values = data.ticketsData.map((d) => d.tickets_sold);

      if (ticketChart) ticketChart.destroy();
      const ctx = document.getElementById("ticketChart").getContext("2d");

      ticketChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Tiket Terjual",
              data: values,
              backgroundColor: "#3b82f6",
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        },
      });
    } catch (err) {
      console.error("❌ Gagal load tiket analytics:", err);
    }
  }

  // --- Update Total Pendapatan ---
  async function updateRevenueChart() {
    const period = revenueSelect.value.toLowerCase();
    try {
      const data = await fetchJSON("/reviews/analytics/admin/data/", { period });
      const labels = data.revenueData.map((d) => d.date);
      const values = data.revenueData.map((d) => d.total_revenue);

      if (revenueChart) revenueChart.destroy();
      const ctx = document.getElementById("revenueChart").getContext("2d");

      revenueChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Pendapatan (Rp)",
              data: values,
              backgroundColor: "#10b981",
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => `Rp ${ctx.parsed.y.toLocaleString("id-ID")}`,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { callback: (v) => `Rp ${v.toLocaleString("id-ID")}` },
            },
          },
        },
      });
    } catch (err) {
      console.error("❌ Gagal load revenue analytics:", err);
    }
  }

  // Listener terpisah
  ticketSelect.addEventListener("change", updateTicketChart);
  revenueSelect.addEventListener("change", updateRevenueChart);

  // Load awal
  updateTicketChart();
  updateRevenueChart();
}
// ====================================
// === USER ANALYTICS =================
// ====================================

function initUserAnalytics() {
  let spendingChart = null;
  let attendanceChart = null;
  let isUpdating = false;
  const periodSelect = document.getElementById("spendingPeriod");

  async function updateCharts() {
    if (isUpdating) return;
    isUpdating = true;

    try {
      const period = periodSelect ? periodSelect.value : "daily";
      const data = await fetchJSON("/reviews/analytics/user/data/", { period });
      console.log("✅ Analytics data:", data);

      const spendingData = data.spendingData || [];
      const attendance = data.attendance || { hadir: 0, tidak_hadir: 0 };

      const labels = spendingData.map((d) => d.date);
      const values = spendingData.map((d) => d.total_spent);

      // --- Hapus semua chart lama dengan cara aman ---
      if (spendingChart && typeof spendingChart.destroy === "function") {
        spendingChart.destroy();
        spendingChart = null;
      }
      if (attendanceChart && typeof attendanceChart.destroy === "function") {
        attendanceChart.destroy();
        attendanceChart = null;
      }

      // --- Buat ulang elemen canvas agar Chart.js benar-benar fresh ---
      const oldSpendingCanvas = document.getElementById("spendingChart");
      const newSpendingCanvas = oldSpendingCanvas.cloneNode(true);
      oldSpendingCanvas.parentNode.replaceChild(newSpendingCanvas, oldSpendingCanvas);

      const oldAttendanceCanvas = document.getElementById("attendanceChart");
      const newAttendanceCanvas = oldAttendanceCanvas.cloneNode(true);
      oldAttendanceCanvas.parentNode.replaceChild(newAttendanceCanvas, oldAttendanceCanvas);

      // === CHART 1: Pengeluaran ===
      const ctx1 = newSpendingCanvas.getContext("2d");
      spendingChart = new Chart(ctx1, {
        type: "bar",
        data: {
          labels: labels.length > 0 ? labels : ["No Data"],
          datasets: [
            {
              label: "Total Pengeluaran (Rp)",
              data: values.length > 0 ? values : [0],
              backgroundColor: "#f59e0b",
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          animation: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => `Rp ${ctx.parsed.y.toLocaleString("id-ID")}`,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                callback: (v) => `Rp ${v.toLocaleString("id-ID")}`,
              },
            },
          },
        },
      });

      // === CHART 2: Kehadiran ===
      const ctx2 = newAttendanceCanvas.getContext("2d");
      attendanceChart = new Chart(ctx2, {
        type: "doughnut",
        data: {
          labels: ["Hadir", "Tidak Hadir"],
          datasets: [
            {
              data: [attendance.hadir, attendance.tidak_hadir],
              backgroundColor: ["#2563eb", "#d1d5db"],
            },
          ],
        },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false } },
        },
      });
    } catch (err) {
      console.error("❌ Gagal load data analytics:", err);
    } finally {
      isUpdating = false;
    }
  }

  if (periodSelect) {
    periodSelect.addEventListener("change", updateCharts);
  }

  updateCharts();
}

// ====================================
// === INITIALIZER ====================
// ====================================

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("revenueChart")) initAdminAnalytics();
  if (document.getElementById("spendingChart")) initUserAnalytics();
});
