import { z } from "zod";

const workbook = z.object({
  id: z.string().uuid(),
  original_filename: z.string(),
  byte_size: z.number().int().nonnegative(),
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
  uploaded_at: z.string().datetime({ offset: true }),
  status: z.literal("stored"),
});
export type Workbook = z.infer<typeof workbook>;

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api${path}`, {
    ...init,
    signal: AbortSignal.timeout(60000),
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = z
      .object({ error: z.object({ message: z.string() }) })
      .safeParse(payload);
    throw new Error(
      error.success
        ? error.data.error.message
        : "The API request failed. Please try again.",
    );
  }
  return payload;
}

export const api = {
  health: async () =>
    z.object({ status: z.literal("ok") }).parse(await request("/health")),
  list: async (offset: number) =>
    z
      .array(workbook)
      .parse(await request(`/workbooks?offset=${offset}&limit=50`)),
  metadata: async (id: string) =>
    workbook.parse(await request(`/workbooks/${id}`)),
  upload: async (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return workbook.parse(
      await request("/workbooks", { method: "POST", body: data }),
    );
  },
};
