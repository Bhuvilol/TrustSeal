const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
});

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return 'N/A';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'N/A';
  }

  return dateTimeFormatter.format(parsed);
}

export function formatDate(value?: string | null): string {
  if (!value) {
    return 'N/A';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'N/A';
  }

  return dateFormatter.format(parsed);
}

export function formatNumber(value?: number | null, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'N/A';
  }

  return value.toFixed(fractionDigits);
}

export function toTitleCase(input: string): string {
  return input
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}

