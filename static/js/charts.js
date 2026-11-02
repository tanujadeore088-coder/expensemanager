/**
 * Expense Manager Tracker - Interactive Visualizations with Chart.js
 * Fetches dynamic live database data from /api/chart-data
 */

document.addEventListener("DOMContentLoaded", function () {
    // Check if chart canvas elements exist on current page (only on dashboard)
    const categoryCanvas = document.getElementById("categoryChart");
    const monthlyCanvas = document.getElementById("monthlyChart");

    if (!categoryCanvas || !monthlyCanvas) {
        return;
    }

    // Color palette for category pie/doughnut chart
    const categoryColors = [
        "#f97316", // Food (Warm Orange)
        "#0ea5e9", // Travel (Sky Blue)
        "#ec4899", // Shopping (Vibrant Pink)
        "#8b5cf6", // Education (Purple)
        "#ef4444", // Bills (Crimson Red)
        "#10b981", // Entertainment (Emerald Green)
        "#06b6d4", // Cyan
        "#f59e0b", // Amber
        "#6366f1", // Indigo
        "#84cc16"  // Lime
    ];

    // Fetch dynamic JSON data from Flask backend API endpoint
    fetch("/api/chart-data")
        .then(response => {
            if (!response.ok) {
                throw new Error("Network response was not ok " + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            // ================================================================
            // 1. Category Breakdown Chart (Doughnut / Pie Chart)
            // ================================================================
            const catLabels = data.categories.labels;
            const catAmounts = data.categories.amounts;

            if (catLabels.length === 0) {
                document.getElementById("categoryChart").classList.add("d-none");
                document.getElementById("categoryChartEmpty").classList.remove("d-none");
            } else {
                new Chart(categoryCanvas.getContext("2d"), {
                    type: "doughnut",
                    data: {
                        labels: catLabels,
                        datasets: [{
                            data: catAmounts,
                            backgroundColor: categoryColors.slice(0, catLabels.length),
                            borderWidth: 2,
                            borderColor: "#ffffff",
                            hoverOffset: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: "bottom",
                                labels: {
                                    usePointStyle: true,
                                    padding: 18,
                                    font: {
                                        family: "'Inter', sans-serif",
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function (context) {
                                        const label = context.label || "";
                                        const value = context.parsed || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                        return ` ${label}: ₹${value.toFixed(2)} (${percentage}%)`;
                                    }
                                }
                            }
                        },
                        cutout: "65%"
                    }
                });
            }

            // ================================================================
            // 2. Monthly Expenses Trend Chart (Bar Chart)
            // ================================================================
            const monthLabels = data.monthly.labels;
            const monthAmounts = data.monthly.amounts;

            if (monthLabels.length === 0) {
                document.getElementById("monthlyChart").classList.add("d-none");
                document.getElementById("monthlyChartEmpty").classList.remove("d-none");
            } else {
                new Chart(monthlyCanvas.getContext("2d"), {
                    type: "bar",
                    data: {
                        labels: monthLabels,
                        datasets: [{
                            label: "Total Spending",
                            data: monthAmounts,
                            backgroundColor: "rgba(79, 70, 229, 0.85)",
                            hoverBackgroundColor: "rgba(67, 56, 202, 1)",
                            borderRadius: 8,
                            borderSkipped: false,
                            maxBarThickness: 45
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
                                    label: function (context) {
                                        return ` Spending: ₹${context.parsed.y.toFixed(2)}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    font: {
                                        family: "'Inter', sans-serif",
                                        size: 12
                                    }
                                }
                            },
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: "#f1f5f9"
                                },
                                ticks: {
                                    font: {
                                        family: "'Inter', sans-serif",
                                        size: 12
                                    },
                                    callback: function (value) {
                                        return "₹" + value;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        })
        .catch(error => {
            console.error("Error loading chart data:", error);
        });
});
