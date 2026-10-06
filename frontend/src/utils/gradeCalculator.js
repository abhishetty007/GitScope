export function calculateGrade(score) {
  if (score === null || score === undefined) return "N/A";
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 70) return "B";
  if (score >= 60) return "C";
  if (score >= 50) return "D";
  return "F";
}

export function getGradeBadgeClass(grade) {
  switch (grade) {
    case "A+":
    case "A":
      return "health-excellent";
    case "B":
      return "health-good";
    case "C":
      return "health-moderate";
    case "D":
    case "F":
      return "health-attention";
    default:
      return "";
  }
}

