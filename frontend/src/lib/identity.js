export async function resolveLocalUser(session, issuer, db) {
  const subject = session?.user?.sub;
  if (typeof subject !== "string" || !subject) return null;
  const normalizedIssuer = new URL(issuer).toString();
  const identity = await db.identity.upsert({
    where: { issuer_subject: { issuer: normalizedIssuer, subject } },
    update: {},
    create: { issuer: normalizedIssuer, subject, user: { create: {} } },
    select: { user: { select: { id: true, createdAt: true } } },
  });
  return identity.user;
}
