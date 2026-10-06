import "server-only";
import { compactAnalysis, analysisSnapshotHash } from "./analysis-snapshot.js";
import { fetchPublicAnalysis, fetchPublicRepository } from "./public-github.js";
import { getDb } from "./db.js";

export const ANALYZER_VERSION = "gitscope-phase3-v1";

const repoWhere = (identity) => ({
  provider_providerRepoId: {
    provider: "github",
    providerRepoId: BigInt(identity.provider_repo_id),
  },
});

async function upsertRepository(db, identity) {
  const now = new Date();
  return db.repository.upsert({
    where: repoWhere(identity),
    update: {
      ownerLogin: identity.owner_login,
      name: identity.name,
      visibility: "public",
      updatedAt: now,
    },
    create: {
      provider: "github",
      providerRepoId: BigInt(identity.provider_repo_id),
      ownerLogin: identity.owner_login,
      name: identity.name,
      visibility: "public",
    },
  });
}

export async function saveAnalysisForUser(userId, owner, repository, dependencies = {}) {
  const fetchAnalysis = dependencies.fetchPublicAnalysis || fetchPublicAnalysis;
  const db = dependencies.db || getDb();
  const { identity, analysis } = await fetchAnalysis(owner, repository);
  const snapshot = compactAnalysis(analysis);
  const snapshotHash = analysisSnapshotHash(snapshot);
  const sourceUpdatedAt = snapshot.repository.updated_at
    ? new Date(snapshot.repository.updated_at)
    : null;

  return db.$transaction(async (tx) => {
    const repo = await upsertRepository(tx, identity);
    const analysisUnique = {
      repositoryId_analyzerVersion_snapshotHash: {
        repositoryId: repo.id,
        analyzerVersion: ANALYZER_VERSION,
        snapshotHash,
      },
    };
    let saved = await tx.analysis.upsert({
      where: analysisUnique,
      update: {},
      create: {
        repositoryId: repo.id,
        analyzerVersion: ANALYZER_VERSION,
        snapshotHash,
        score: snapshot.health.score,
        result: snapshot,
        sourceUpdatedAt: sourceUpdatedAt && !Number.isNaN(sourceUpdatedAt.getTime()) ? sourceUpdatedAt : null,
      },
      select: { id: true },
    });

    await tx.$queryRaw`SELECT pg_advisory_xact_lock(hashtextextended(${saved.id}, 0))`;
    saved = await tx.analysis.findUnique({ where: { id: saved.id }, select: { id: true } });
    if (!saved) {
      saved = await tx.analysis.upsert({
        where: analysisUnique,
        update: {},
        create: {
          repositoryId: repo.id,
          analyzerVersion: ANALYZER_VERSION,
          snapshotHash,
          score: snapshot.health.score,
          result: snapshot,
          sourceUpdatedAt: sourceUpdatedAt && !Number.isNaN(sourceUpdatedAt.getTime()) ? sourceUpdatedAt : null,
        },
        select: { id: true },
      });
    }

    const association = await tx.savedAnalysis.createMany({
      data: [{ userId, analysisId: saved.id }],
      skipDuplicates: true,
    });
    return { analysisId: saved.id, alreadySaved: association.count === 0 };
  }, { isolationLevel: "Serializable" });
}

export async function listSavedAnalyses(userId, db = getDb()) {
  return db.savedAnalysis.findMany({
    where: { userId },
    orderBy: { createdAt: "desc" },
    take: 100,
    select: {
      createdAt: true,
      analysis: {
        select: {
          id: true,
          score: true,
          createdAt: true,
          result: true,
          repository: { select: { ownerLogin: true, name: true } },
        },
      },
    },
  });
}

export async function getSavedAnalysis(userId, analysisId, db = getDb()) {
  return db.savedAnalysis.findUnique({
    where: { userId_analysisId: { userId, analysisId } },
    select: {
      createdAt: true,
      analysis: {
        select: {
          id: true,
          score: true,
          createdAt: true,
          result: true,
          repository: { select: { ownerLogin: true, name: true } },
        },
      },
    },
  });
}

export async function deleteSavedAnalysis(userId, analysisId, db = getDb()) {
  return db.$transaction(async (tx) => {
    await tx.$queryRaw`SELECT pg_advisory_xact_lock(hashtextextended(${analysisId}, 0))`;
    const owned = await tx.savedAnalysis.findUnique({
      where: { userId_analysisId: { userId, analysisId } },
      select: { analysisId: true },
    });
    if (!owned) return false;

    await tx.savedAnalysis.delete({
      where: { userId_analysisId: { userId, analysisId } },
    });
    const remaining = await tx.savedAnalysis.count({ where: { analysisId } });
    if (remaining === 0) {
      await tx.analysis.deleteMany({ where: { id: analysisId } });
    }
    return true;
  }, { isolationLevel: "Serializable" });
}

export async function trackPublicRepository(userId, owner, repository, dependencies = {}) {
  const resolveRepository = dependencies.fetchPublicRepository || fetchPublicRepository;
  const db = dependencies.db || getDb();
  const identity = await resolveRepository(owner, repository);
  return db.$transaction(async (tx) => {
    const repo = await upsertRepository(tx, identity);
    await tx.trackedRepository.createMany({
      data: [{ userId, repositoryId: repo.id }],
      skipDuplicates: true,
    });
    return {
      repositoryId: repo.id,
      ownerLogin: repo.ownerLogin,
      name: repo.name,
    };
  }, { isolationLevel: "Serializable" });
}

export async function listTrackedRepositories(userId, db = getDb()) {
  return db.trackedRepository.findMany({
    where: { userId },
    orderBy: { createdAt: "desc" },
    select: {
      createdAt: true,
      repository: {
        select: {
          id: true,
          providerRepoId: true,
          ownerLogin: true,
          name: true,
          visibility: true,
        },
      },
    },
  });
}

export async function removeTrackedRepository(userId, repositoryId, db = getDb()) {
  return db.trackedRepository.deleteMany({
    where: { userId, repositoryId },
  }).then((result) => result.count > 0);
}
