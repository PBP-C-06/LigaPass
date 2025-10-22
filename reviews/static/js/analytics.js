async function fetchJSON(url, params = {}) {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${url}?${query}`);
  return response.json();
}

// ====================================
// === ADMIN ANALYTICS ===============
// ====================================
function initAdminAnalytics() {
  const matchSelect = document.getElementById("matchFilter");
  const seatSelect = document.getElementById("seatFilter");

  let revenueChart, occupancyChart;

  async function updateCharts() {
    const data = await fetchJSON("/reviews/analytics/admin/data/", {
      match_id: matchSelect.value,
      seat: seatSelect.value,
    });

    const labels = data.revenue_data.map(
      (d) => `${d.ticket_type__match__home_team__name} vs ${d.ticket_type__match__away_team__name}`
    );
    const revenues = data.revenue_data.map((d) => d.total_revenue);
    const occupancies = data.occupancy_data.map((d) => d.occupancy);

    // destroy old charts
    if (revenueChart) revenueChart.destroy();
    if (occupancyChart) occupancyChart.destroy();

    // Revenue Chart
    const ctx1 = document.getElementById("revenueChart").getContext("2d");
    revenueChart = new Chart(ctx1, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Pendapatan (Rp)",
          data: revenues,
          backgroundColor: "#60a5fa",
        }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });

    // Occupancy Chart
    const ctx2 = document.getElementById("occupancyChart").getContext("2d");
    occupancyChart = new Chart(ctx2, {
      type: "doughnut",
      data: {
        labels: data.occupancy_data.map((d) => `${d.seat_category}`),
        datasets: [{
          data: occupancies,
          backgroundColor: ["#3b82f6", "#10b981", "#f59e0b"],
        }],
      },
      options: { responsive: true },
    });
  }

  matchSelect.addEventListener("change", updateCharts);
  seatSelect.addEventListener("change", updateCharts);
  updateCharts();
}


// ====================================
// === USER ANALYTICS ================
// ====================================
function initUserAnalytics() {
  let spendingChart, seatChart;

  async function updateCharts() {
    const data = await fetchJSON("/reviews/analytics/user/data/");

    const months = data.spending_data.map((d) => `Bulan ${d.month}`);
    const spendings = data.spending_data.map((d) => d.total_spent);
    const seatLabels = data.seat_count.map((d) => d.ticket_type__seat_category);
    const seatValues = data.seat_count.map((d) => d.count);

    // destroy old charts
    if (spendingChart) spendingChart.destroy();
    if (seatChart) seatChart.destroy();

    // Spending Chart
    const ctx1 = document.getElementById("spendingChart").getContext("2d");
    spendingChart = new Chart(ctx1, {
      type: "bar",
      data: {
        labels: months,
        datasets: [{
          label: "Total Pengeluaran (Rp)",
          data: spendings,
          backgroundColor: "#f87171",
        }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });

    // Seat Category Chart
    const ctx2 = document.getElementById("seatChart").getContext("2d");
    seatChart = new Chart(ctx2, {
      type: "pie",
      data: {
        labels: seatLabels,
        datasets: [{
          data: seatValues,
          backgroundColor: ["#3b82f6", "#10b981", "#f59e0b"],
        }],
      },
      options: { responsive: true },
    });
  }

  updateCharts();
}
