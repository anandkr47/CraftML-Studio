// No unified API for training comparison; return a sensible placeholder
export async function compareTrainingJobs(jobA: string, jobB: string) {
  return {
    status: 'success',
    comparison: `Comparison for training jobs ${jobA} vs ${jobB} is not available.`,
  } as any;
}
