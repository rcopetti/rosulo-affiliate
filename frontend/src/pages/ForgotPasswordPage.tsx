import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AxiosError } from 'axios';
import {
  confirmPasswordReset,
  requestPasswordReset,
  verifyPasswordResetCode,
  ResetUserType,
} from '@/api/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';

type Step = 'email' | 'code' | 'password' | 'done';

interface ForgotPasswordPageProps {
  userType: ResetUserType;
  loginPath: string;
  title: string;
}

export function ForgotPasswordPage({ userType, loginPath, title }: ForgotPasswordPageProps) {
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submitEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset({ email, user_type: userType });
      setNotice('If that email is registered, a 6-digit code is on its way.');
      setStep('code');
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset({ email, user_type: userType });
      setCode('');
      setNotice('If that email is registered, a new code is on its way. Previous codes no longer work.');
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await verifyPasswordResetCode({ email, user_type: userType, code });
      setResetToken(res.reset_token);
      setNotice(null);
      setStep('password');
    } catch (err) {
      const detail = (err as AxiosError<{ detail?: string }>).response?.data?.detail;
      setError(
        detail === 'locked'
          ? 'Too many attempts. Please wait 5 minutes and request a new code.'
          : 'Invalid or expired code. Check the code and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const submitPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== passwordConfirm) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await confirmPasswordReset({
        email,
        user_type: userType,
        reset_token: resetToken,
        new_password: password,
      });
      setStep('done');
    } catch {
      setError('This reset has expired. Please request a new code.');
      setStep('email');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
        {notice && <p className="mb-4 text-sm text-slate-600">{notice}</p>}

        {step === 'email' && (
          <form onSubmit={submitEmail} className="space-y-4">
            <Input
              id="reset-email"
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button type="submit" isLoading={loading} className="w-full">
              Send reset code
            </Button>
          </form>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="space-y-4">
            <Input
              id="reset-code"
              label="6-digit code"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              required
            />
            <Button type="submit" isLoading={loading} className="w-full">
              Verify code
            </Button>
            <Button type="button" variant="secondary" onClick={resend} isLoading={loading} className="w-full">
              Resend code
            </Button>
          </form>
        )}

        {step === 'password' && (
          <form onSubmit={submitPassword} className="space-y-4">
            <Input
              id="reset-password"
              label="New password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Input
              id="reset-password-confirm"
              label="Confirm new password"
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
            />
            <Button type="submit" isLoading={loading} className="w-full">
              Set new password
            </Button>
          </form>
        )}

        {step === 'done' && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">Your password has been updated. You can now log in.</p>
            <Link to={loginPath} className="text-brand-600 hover:underline">
              Back to login
            </Link>
          </div>
        )}

        {step !== 'done' && (
          <p className="mt-4 text-center text-sm text-slate-600">
            <Link to={loginPath} className="text-brand-600 hover:underline">
              Back to login
            </Link>
          </p>
        )}
      </Card>
    </div>
  );
}

export function AffiliateForgotPasswordPage() {
  return <ForgotPasswordPage userType="affiliate" loginPath="/login" title="Reset affiliate password" />;
}

export function AdminForgotPasswordPage() {
  return <ForgotPasswordPage userType="tenant" loginPath="/admin/login" title="Reset admin password" />;
}
