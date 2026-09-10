import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Button } from '@/components/ui/Button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /Click me/i })).toBeInTheDocument();
  });

  it('is disabled when isLoading', () => {
    render(<Button isLoading>Loading</Button>);
    expect(screen.getByRole('button', { name: /Loading/i })).toBeDisabled();
  });
});
