'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Search, Loader2, Globe } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Badge } from '@/components/ui/badge';

import { reconAPI } from '@/lib/api';
import { ScanResponse, ReconModule } from '@/types/recon';

// Module configuration with descriptions and icons
/**
 * Module configuration for scan form UI.
 * 
 * CLEANUP NOTE (2025-10-06):
 * - Removed CLOUD_SSL module (not implemented)
 * - Only SUBFINDER is currently functional
 * - Future modules kept as disabled for reference
 */
const MODULE_CONFIG = {
  [ReconModule.SUBFINDER]: {
    name: 'Subfinder',
    description: 'OSINT-based subdomain discovery using passive sources',
    icon: Globe,
    color: 'bg-blue-600',
    enabled: true,
    recommended: true,
  },
  // Future modules (disabled until backend implements them):
  // [ReconModule.DNS_BRUTEFORCE]: {
  //   name: 'DNS Bruteforce',
  //   description: 'Active DNS brute force enumeration (Coming Soon)',
  //   icon: Zap,
  //   color: 'bg-slate-600',
  //   enabled: false,
  //   recommended: false,
  // },
  // [ReconModule.HTTP_PROBE]: {
  //   name: 'HTTP Probe',
  //   description: 'Web service discovery and fingerprinting (Coming Soon)',
  //   icon: Cloud,
  //   color: 'bg-purple-600',
  //   enabled: false,
  //   recommended: false,
  // },
};

// Form validation schema
const scanFormSchema = z.object({
  domain: z
    .string()
    .min(1, 'Domain is required')
    .max(253, 'Domain too long')
    .regex(
      /^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$/,
      'Invalid domain format'
    )
    .transform(val => val.toLowerCase().trim()),
  modules: z.array(z.nativeEnum(ReconModule)).min(1, 'Select at least one module'),
});

type ScanFormData = z.infer<typeof scanFormSchema>;

interface DomainScanFormProps {
  onScanStarted?: (response: ScanResponse) => void;
}

export default function DomainScanForm({ onScanStarted }: DomainScanFormProps) {
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<ScanFormData>({
    resolver: zodResolver(scanFormSchema),
    defaultValues: {
      domain: '',
      modules: [ReconModule.SUBFINDER], // Default to subfinder only
    },
  });

  const selectedModules = form.watch('modules');

  const toggleModule = (module: ReconModule) => {
    const current = selectedModules || [];
    const updated = current.includes(module)
      ? current.filter(m => m !== module)
      : [...current, module];
    form.setValue('modules', updated);
  };

  const selectRecommended = () => {
    const recommended = Object.entries(MODULE_CONFIG)
      .filter(([, config]) => config.recommended && config.enabled)
      .map(([moduleKey]) => moduleKey as ReconModule);
    form.setValue('modules', recommended);
  };

  const onSubmit = async (data: ScanFormData) => {
    try {
      setIsLoading(true);
      
      const response = await reconAPI.startSubdomainScan(data);
      
      const moduleNames = data.modules.map(m => MODULE_CONFIG[m].name).join(', ');
      toast.success(`Scan started for ${data.domain} using ${moduleNames}!`);
      
      // Reset form
      form.reset();
      
      // Notify parent component
      onScanStarted?.(response);
      
    } catch (error: unknown) {
      const message = error && typeof error === 'object' && 'response' in error
        ? (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Scan failed to start'
        : 'Scan failed to start';
      
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Search className="h-5 w-5" />
          <span>Start Multi-Module Reconnaissance</span>
        </CardTitle>
        <CardDescription>
          Configure and launch distributed reconnaissance using multiple discovery techniques.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <FormField
              control={form.control}
              name="domain"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Target Domain</FormLabel>
                  <FormControl>
                    <Input 
                      placeholder="example.com" 
                      {...field}
                      disabled={isLoading}
                    />
                  </FormControl>
                  <FormDescription>
                    Enter the apex domain you want to scan (e.g., example.com)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="modules"
              render={() => (
                <FormItem>
                  <div className="flex items-center justify-between">
                    <FormLabel>Reconnaissance Modules</FormLabel>
                    <Button 
                      type="button" 
                      variant="outline" 
                      size="sm" 
                      onClick={selectRecommended}
                      disabled={isLoading}
                    >
                      Select Recommended
                    </Button>
                  </div>
                  <FormDescription>
                    Choose which discovery techniques to use for maximum coverage
                  </FormDescription>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.entries(MODULE_CONFIG).map(([moduleKey, config]) => {
                      const moduleEnum = moduleKey as ReconModule;
                      const isSelected = selectedModules?.includes(moduleEnum);
                      const IconComponent = config.icon;
                      
                      return (
                        <div
                          key={moduleEnum}
                          className={`
                            p-4 border rounded-lg cursor-pointer transition-all
                            ${isSelected 
                              ? 'border-primary bg-primary/5 ring-1 ring-primary/20' 
                              : 'border-muted hover:border-muted-foreground/50'
                            }
                            ${!config.enabled ? 'opacity-50 cursor-not-allowed' : ''}
                          `}
                          onClick={() => config.enabled && toggleModule(moduleEnum)}
                        >
                          <div className="flex items-start space-x-3">
                            <div className={`p-2 rounded-lg ${config.color} ${!config.enabled ? 'grayscale' : ''}`}>
                              <IconComponent className="h-4 w-4 text-white" />
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-1">
                                <h3 className="font-medium text-sm">{config.name}</h3>
                                {config.recommended && config.enabled && (
                                  <Badge variant="outline" className="text-xs">Recommended</Badge>
                                )}
                                {!config.enabled && (
                                  <Badge variant="secondary" className="text-xs">Coming Soon</Badge>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground">
                                {config.description}
                              </p>
                            </div>
                            {isSelected && config.enabled && (
                              <div className="w-4 h-4 rounded-full bg-primary flex items-center justify-center">
                                <div className="w-2 h-2 rounded-full bg-white"></div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <Button 
              type="submit" 
              disabled={isLoading || !selectedModules?.length}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting Scan...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Start Scan ({selectedModules?.length || 0} module{selectedModules?.length === 1 ? '' : 's'})
                </>
              )}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
