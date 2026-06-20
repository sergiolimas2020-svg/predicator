module.exports = async function handler(req, res) {
  const delay = Number(process.env.FREE_SIGNAL_DELAY_HOURS || 1);
  res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=300");
  res.status(200).json({
    free_signal_delay_hours: Number.isFinite(delay) && delay >= 0 ? delay : 1
  });
};
