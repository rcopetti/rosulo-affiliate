import { z } from 'zod';

export const emailSchema = z.string().email();

export const passwordSchema = z.string().min(8, 'Password must be at least 8 characters');

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Password is required'),
});

export const registerSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  name: z.string().min(1, 'Name is required'),
  country: z.string().min(1, 'Country is required'),
  state: z.string().optional(),
  tax_status: z.string().optional(),
  tax_form_type: z.string().optional(),
  paypal_email: z.string().email().optional().or(z.literal('')),
});

export const acceptInviteSchema = z.object({
  token: z.string().min(1, 'Invite token is required'),
});

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
