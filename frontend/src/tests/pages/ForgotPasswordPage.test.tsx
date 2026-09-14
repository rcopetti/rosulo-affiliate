import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AffiliateForgotPasswordPage } from '@/pages/ForgotPasswordPage';
import { requestPasswordReset, verifyPasswordResetCode, confirmPasswordReset } from '@/api/auth';

vi.mock('@/api/auth', () => ({
  requestPasswordReset: vi.fn().mockResolvedValue(undefined),
  verifyPasswordResetCode: vi.fn(),
  confirmPasswordReset: vi.fn().mockResolvedValue(undefined),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <AffiliateForgotPasswordPage />
    </MemoryRouter>
  );

describe('AffiliateForgotPasswordPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('requests a code and advances to the code step', async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await waitFor(() =>
      expect(requestPasswordReset).toHaveBeenCalledWith({ email: 'a@b.com', user_type: 'affiliate' })
    );
    expect(await screen.findByLabelText(/^6-digit code/i)).toBeInTheDocument();
  });

  it('shows a generic error on a wrong code', async () => {
    vi.mocked(verifyPasswordResetCode).mockRejectedValue({
      response: { data: { detail: 'invalid_or_expired_code' } },
    });
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await userEvent.type(await screen.findByLabelText(/^6-digit code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: /verify code/i }));
    expect(await screen.findByText(/invalid or expired code/i)).toBeInTheDocument();
  });

  it('shows lockout copy when the code is locked', async () => {
    vi.mocked(verifyPasswordResetCode).mockRejectedValue({
      response: { data: { detail: 'locked' } },
    });
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await userEvent.type(await screen.findByLabelText(/^6-digit code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: /verify code/i }));
    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
  });

  it('advances to password step and confirms reset', async () => {
    vi.mocked(verifyPasswordResetCode).mockResolvedValue({ reset_token: 'tok-1' });
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await userEvent.type(await screen.findByLabelText(/^6-digit code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: /verify code/i }));
    await userEvent.type(await screen.findByLabelText(/^new password/i), 'newpass456');
    await userEvent.type(screen.getByLabelText(/^confirm new password/i), 'newpass456');
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
    await waitFor(() =>
      expect(confirmPasswordReset).toHaveBeenCalledWith({
        email: 'a@b.com',
        user_type: 'affiliate',
        reset_token: 'tok-1',
        new_password: 'newpass456',
      })
    );
    expect(await screen.findByText(/password has been updated/i)).toBeInTheDocument();
  });
});
