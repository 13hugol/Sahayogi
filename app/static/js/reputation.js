// Refresh reputation blocks on the current page every 60 seconds
document.addEventListener("DOMContentLoaded", () => {
  const blocks = document.querySelectorAll('.reputation-block[data-user-id]');
  if (blocks.length > 0) {
    setInterval(() => {
      blocks.forEach(block => {
        const userId = block.dataset.userId;
        fetch(`/api/reputation/${userId}`)
          .then(r => {
            if (r.ok) return r.json();
            throw new Error("Failed to fetch reputation");
          })
          .then(data => {
            if (!data.score) return;
            const scoreEl = block.querySelector('.score-value');
            if (scoreEl) scoreEl.textContent = data.score;
            
            const countEl = block.querySelector('.review-count');
            if (countEl) countEl.textContent = `(${data.count} review${data.count !== 1 ? 's' : ''})`;
            
            const tierEl = block.querySelector('.tier-badge');
            if (tierEl) {
              tierEl.textContent = data.tier;
              tierEl.className = `tier-badge tier-${data.tier.toLowerCase().replace(' ', '-')}`;
            }

            const stars = block.querySelectorAll('.star');
            if (stars.length === 5) {
              const roundedScore = Math.round(data.score);
              stars.forEach((star, index) => {
                if (index < roundedScore) {
                  star.classList.add('filled');
                } else {
                  star.classList.remove('filled');
                }
              });
            }

            const tooltipEl = block.querySelector('.score-tooltip');
            if (tooltipEl) tooltipEl.title = `Score: ${data.score} from ${data.count} reviews`;
          })
          .catch(err => console.error(err));
      });
    }, 60000);
  }
});
