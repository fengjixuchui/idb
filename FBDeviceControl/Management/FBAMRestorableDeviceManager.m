/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#import "FBAMRestorableDeviceManager.h"

#import "FBAMDevice+Private.h"
#import "FBDeviceControlError.h"
#import "FBDeviceControlFrameworkLoader.h"
#import "FBAMRestorableDevice.h"

@interface FBAMRestorableDeviceManager ()

@property (nonatomic, strong, readonly) dispatch_queue_t queue;
@property (nonatomic, assign, readonly) AMDCalls calls;
@property (nonatomic, assign, readwrite) int registrationID;

@end

static NSString *NotificationTypeToString(AMRestorableDeviceNotificationType status)
{
  switch (status) {
    case AMRestorableDeviceNotificationTypeConnected:
      return @"connected";
    case AMRestorableDeviceNotificationTypeDisconnected:
      return @"disconnected";
    default:
      return @"unknown";
  }
}

static void FB_AMRestorableDeviceListenerCallback(AMRestorableDeviceRef device, AMRestorableDeviceNotificationType status, void *context)
{
  FBAMRestorableDeviceManager *manager = (__bridge FBAMRestorableDeviceManager *)context;
  id<FBControlCoreLogger> logger = manager.logger;
  AMRestorableDeviceState deviceState = manager.calls.RestorableDeviceGetState(device);
  FBiOSTargetState targetState = [FBAMRestorableDevice targetStateForDeviceState:deviceState];
  NSString *identifier = [@(manager.calls.RestorableDeviceGetECID(device)) stringValue];
  [logger logFormat:@"%@ %@ in state %@", device, NotificationTypeToString(status), FBiOSTargetStateStringFromState(targetState)];
  switch (deviceState) {
    case AMRestorableDeviceStateBootedOS:
    case AMRestorableDeviceStateUnknown:
      [logger logFormat:@"Ignoring %@ as a restorable device as it is %@", device, FBiOSTargetStateStringFromState(targetState)];
      return;
    default:
      break;
  }
  switch (status) {
    case AMRestorableDeviceNotificationTypeConnected:
      [manager deviceConnected:device identifier:identifier info:nil];
      return;
    case AMRestorableDeviceNotificationTypeDisconnected:
      [manager deviceDisconnected:device identifier:identifier];
      return;
    default:
      [logger logFormat:@"Unknown Restorable Notification %d", status];
      return;
  }
}

@implementation FBAMRestorableDeviceManager

#pragma mark Initializers

- (instancetype)initWithLogger:(id<FBControlCoreLogger>)logger
{
  self = [super initWithLogger:logger];
  if (!self) {
    return nil;
  }

  _queue = dispatch_get_main_queue();
  _calls = FBDeviceControlFrameworkLoader.amDeviceCalls;

  return self;
}

#pragma mark Abstract Implementation

- (BOOL)startListeningWithError:(NSError **)error
{
  int registrationID = self.calls.RestorableDeviceRegisterForNotifications(
    FB_AMRestorableDeviceListenerCallback,
    (void *) CFBridgingRetain(self),
    0,
    0
  );
  if (registrationID < 1) {
    return [[FBDeviceControlError
      describeFormat:@"AMRestorableDeviceRegisterForNotifications failed with %d", registrationID]
      failBool:error];
  }
  self.registrationID = registrationID;
  return YES;
}

- (BOOL)stopListeningWithError:(NSError **)error
{
  int registrationID = self.registrationID;
  self.registrationID = 0;
  if (registrationID < 1) {
    return [[FBDeviceControlError
      describe:@"Cannot unregister from AMRestorableDevice notifications, no subscription"]
      failBool:error];
  }

  // Return of AMRestorableDeviceUnregisterForNotifications seems to be some random number.
  // However, giving invalid registrationID is fine and we still get logging.
  self.calls.RestorableDeviceUnregisterForNotifications(registrationID);
  return YES;
}

- (FBAMRestorableDevice *)constructPublic:(AMRestorableDeviceRef)privateDevice identifier:(NSString *)identifier info:(NSDictionary<NSString *,id> *)info
{
  return [[FBAMRestorableDevice alloc] initWithCalls:self.calls restorableDevice:privateDevice];
}

+ (void)updatePublicReference:(FBAMRestorableDevice *)publicDevice privateDevice:(AMRestorableDeviceRef)privateDevice identifier:(NSString *)identifier info:(NSDictionary<NSString *,id> *)info
{
  publicDevice.restorableDevice = privateDevice;
}

+ (AMRestorableDeviceRef)extractPrivateReference:(FBAMRestorableDevice *)publicDevice
{
  return publicDevice.restorableDevice;
}

@end
