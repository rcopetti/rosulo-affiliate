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
  postal_code: z.string().min(1, 'Postal code is required'),
  tax_status: z.enum(['us_person', 'foreign_person']).default('us_person'),
  tax_entity_type: z.enum(['individual', 'business']).default('individual'),
  business_name: z.string().optional(),
  tax_form_type: z.string().optional(),
  paypal_email: z.string().email('Enter a valid PayPal email').optional().or(z.literal('')),
});

export const acceptInviteSchema = z.object({
  token: z.string().min(1, 'Invite token is required'),
});

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
