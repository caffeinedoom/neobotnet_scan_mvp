// Authentication types that match the backend Pydantic schemas

export interface UserRegister {
  email: string;
  password: string;
  full_name?: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse {
  message: string;
  expires_in: number;
  user?: UserResponse; // Backend returns user data in login response
}

export interface UserResponse {
  id: string;
  email: string;
  full_name?: string;
  created_at: string;
  email_confirmed_at?: string;
}

export interface AuthState {
  user: UserResponse | null;
  token: string | null; // Now represents cookie-based auth status
  isLoading: boolean;
  isAuthenticated: boolean;
}

export interface RegisterResponse {
  message: string;
  user?: UserResponse;
} 