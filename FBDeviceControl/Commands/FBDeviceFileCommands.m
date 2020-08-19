/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#import "FBDeviceFileCommands.h"

#import "FBDevice.h"
#import "FBDevice+Private.h"
#import "FBDeviceControlError.h"
#import "FBAFCConnection.h"

@interface FBDeviceFileContainer ()

@property (nonatomic, strong, readonly) dispatch_queue_t queue;
@property (nonatomic, strong, readonly) FBAFCConnection *connection;

@end

@implementation FBDeviceFileContainer

- (instancetype)initWithAFCConnection:(FBAFCConnection *)connection queue:(dispatch_queue_t)queue
{
  self = [super init];
  if (!self) {
    return nil;
  }

  _connection = connection;
  _queue = queue;

  return self;
}

- (FBFuture<NSNull *> *)copyPathsOnHost:(NSArray<NSURL *> *)paths toDestination:(NSString *)destinationPath
{
  return [self handleAFCOperation:^ NSNull * (FBAFCConnection *afc, NSError **error) {
    for (NSURL *path in paths) {
      BOOL success = [afc copyFromHost:path toContainerPath:destinationPath error:error];
      if (!success) {
        return nil;
      }
    }
    return NSNull.null;
  }];
}

- (FBFuture<NSString *> *)copyItemInContainer:(NSString *)containerPath toDestinationOnHost:(NSString *)destinationPath
{
  return [[self
    readFileFromPathInContainer:containerPath]
    onQueue:self.queue fmap:^FBFuture<NSString *> *(NSData *fileData) {
     NSError *error;
     if (![fileData writeToFile:destinationPath options:0 error:&error]) {
       return [[[FBDeviceControlError
        describeFormat:@"Failed to write data to file at path %@", destinationPath]
        causedBy:error]
        failFuture];
     }
     return [FBFuture futureWithResult:destinationPath];
   }];

}

- (FBFuture<NSNull *> *)createDirectory:(NSString *)directoryPath
{
  return [self handleAFCOperation:^ NSNull * (FBAFCConnection *afc, NSError **error) {
    BOOL success = [afc createDirectory:directoryPath error:error];
    if (!success) {
      return nil;
    }
    return NSNull.null;
  }];
}

- (FBFuture<NSNull *> *)movePaths:(NSArray<NSString *> *)originPaths toDestinationPath:(NSString *)destinationPath
{
  return [self handleAFCOperation:^ NSNull * (FBAFCConnection *afc, NSError **error) {
    for (NSString *originPath in originPaths) {
      BOOL success = [afc renamePath:originPath destination:destinationPath error:error];
      if (!success) {
        return nil;
      }
    }
    return NSNull.null;
  }];
}

- (FBFuture<NSNull *> *)removePaths:(NSArray<NSString *> *)paths
{
  return [self handleAFCOperation:^ NSNull * (FBAFCConnection *afc, NSError **error) {
    for (NSString *path in paths) {
      BOOL success = [afc removePath:path recursively:YES error:error];
      if (!success) {
        return nil;
      }
    }
    return NSNull.null;
  }];
}

- (FBFuture<NSArray<NSString *> *> *)contentsOfDirectory:(NSString *)path
{
  return [self handleAFCOperation:^ NSArray<NSString *> * (FBAFCConnection *afc, NSError **error) {
    return [afc contentsOfDirectory:path error:error];
  }];
}

#pragma mark Private

- (FBFuture<NSData *> *)readFileFromPathInContainer:(NSString *)path
{
  return [self handleAFCOperation:^ NSData * (FBAFCConnection *afc, NSError **error) {
    return [afc contentsOfPath:path error:error];
  }];
}

- (FBFuture *)handleAFCOperation:(id(^)(FBAFCConnection *, NSError **))operationBlock
{
  return [FBFuture
  onQueue:self.queue resolveValue:^(NSError **error) {
      return operationBlock(self.connection, error);
  }];
}

@end

@interface FBDeviceFileCommands ()

@property (nonatomic, strong, readonly) FBDevice *device;
@property (nonatomic, assign, readonly) AFCCalls afcCalls;

@end

@implementation FBDeviceFileCommands

#pragma mark Initializers

+ (instancetype)commandsWithTarget:(FBDevice *)target afcCalls:(AFCCalls)afcCalls
{
  return [[self alloc] initWithDevice:target afcCalls:afcCalls];
}

+ (instancetype)commandsWithTarget:(FBDevice *)target
{
  return [self commandsWithTarget:target afcCalls:FBAFCConnection.defaultCalls];
}

- (instancetype)initWithDevice:(FBDevice *)device afcCalls:(AFCCalls)afcCalls
{
  self = [super init];
  if (!self) {
    return nil;
  }

  _device = device;
  _afcCalls = afcCalls;

  return self;
}

#pragma mark FBFileCommands

- (FBFutureContext<id<FBFileContainer>> *)fileCommandsForContainerApplication:(NSString *)bundleID
{
  return [[self.device
    houseArrestAFCConnectionForBundleID:bundleID afcCalls:self.afcCalls]
    onQueue:self.device.asyncQueue pend:^ FBFuture<id<FBFileContainer>> * (FBAFCConnection *connection) {
      return [FBFuture futureWithResult:[[FBDeviceFileContainer alloc] initWithAFCConnection:connection queue:self.device.asyncQueue]];
    }];
}

- (FBFutureContext<id<FBFileContainer>> *)fileCommandsForRootFilesystem
{
  return [[FBControlCoreError
    describeFormat:@"%@ not supported on devices, requires a rooted device", NSStringFromSelector(_cmd)]
    failFutureContext];
}

- (FBFutureContext<id<FBFileContainer>> *)fileCommandsForMediaDirectory
{
  return [[self.device
    startAFCService:@"com.apple.afc"]
    onQueue:self.device.asyncQueue pend:^ FBFuture<id<FBFileContainer>> * (FBAFCConnection *connection) {
      return [FBFuture futureWithResult:[[FBDeviceFileContainer alloc] initWithAFCConnection:connection queue:self.device.asyncQueue]];
    }];
}

@end
