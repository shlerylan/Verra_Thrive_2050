export const date = (value: string) => new Date(value).toLocaleString("en-GB");
export const size = (value: number) => `${value.toLocaleString("en-GB")} bytes`;
export const message = (error: unknown) =>
  error instanceof Error && error.name !== "ZodError"
    ? error.message
    : "An unexpected API response was received.";
export const key = (id: string, version: string) =>
  JSON.stringify([id, version]);
export const availability = {
  unavailable: "Unavailable",
  file_intake_only: "File intake only",
  prototype_calculation: "Calculation preview",
  calculation_ready: "Ready for calculation",
};
