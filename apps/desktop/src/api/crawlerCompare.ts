// No unified API for crawler comparison; return a sensible placeholder
export async function compareCrawlJobs(jobA: string, jobB: string) {
  return {
    status: 'success',
    comparison: `Comparison for crawl jobs ${jobA} vs ${jobB} is not available.`,
  } as any;
}
